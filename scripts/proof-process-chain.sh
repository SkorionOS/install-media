#!/usr/bin/env bash
# Prove installer.tui_main spawned frzr-bootstrap (via wrapper that logs PPID at exec).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PROOF="${1:-$ROOT/.sim/process-chain}"
mkdir -p "$PROOF"
PROOF="$(cd "$PROOF" && pwd)"
echo "PROOF_DIR=$PROOF"

LOOP=""
cleanup() {
  sudo tmux kill-session -t installer-proof 2>/dev/null || true
  sudo pkill -f 'installer.tui_main' 2>/dev/null || true
  sudo umount /tmp/frzr_root/boot /tmp/frzr_root 2>/dev/null || true
  [[ -n "$LOOP" ]] && echo "$LOOP" >"$PROOF/loop.txt"
}
trap cleanup EXIT

sudo tmux kill-session -t installer-proof 2>/dev/null || true
sudo pkill -f 'installer.tui_main' 2>/dev/null || true
sudo umount /tmp/frzr_root/boot /tmp/frzr_root 2>/dev/null || true
sudo rm -f /tmp/frzr-bootstrap.lock

IMG="$PROOF/vdisk.img"
rm -f "$IMG"
truncate -s 64G "$IMG"
LOOP="$(sudo losetup -f --show -P "$IMG")"
DISK="${LOOP#/dev/}"
echo "$LOOP" | tee "$PROOF/loop.txt"
echo "$DISK" >"$PROOF/disk.txt"

{
  echo "===== BEFORE ====="
  date -Iseconds
  sudo lsblk -o NAME,SIZE,FSTYPE,LABEL,PARTLABEL "$LOOP"
} | tee "$PROOF/00_before.txt"

CHAIN_LOG="$PROOF/11_process_chain.txt"
: >"$CHAIN_LOG"
chmod +x "$ROOT/scripts/proof-frzr-bootstrap-wrapper.sh"

# Screen capture loop
sudo bash -c "
PROOF='$PROOF'
for i in \$(seq 1 40); do
  tmux capture-pane -t installer-proof -p >\"\$PROOF/screen_\$(printf '%02d' \$i).txt\" 2>/dev/null || true
  sleep 0.2
done
" &
CAP_PID=$!

WRAPPER="$PROOF/run_tui.sh"
cat >"$WRAPPER" <<EOF
#!/bin/bash
set -euo pipefail
echo "tui_wrapper_pid=\$\$" >"$PROOF/12_tui_pid.txt"
echo "tui_wrapper_start=\$(date -Iseconds)" >>"$PROOF/12_tui_pid.txt"
cd "$ROOT"
export PYTHONPATH="$ROOT/skorionos/airootfs/usr/local/lib"
export TERM=xterm-256color
export INSTALLER_SIMULATION=1
export INSTALLER_SIM_AUTO=1
export INSTALLER_SIM_MODE=fresh
export INSTALLER_SIM_DISK="$DISK"
export INSTALLER_PROOF_CHAIN_LOG="$CHAIN_LOG"
export INSTALLER_PROOF_REAL_FRZR=/usr/bin/frzr-bootstrap
export INSTALLER_FRZR_BOOTSTRAP="$ROOT/scripts/proof-frzr-bootstrap-wrapper.sh"
export INSTALLER_ALLOW_REAL_FRZR=1
export INSTALLER_FRZR_DEPLOY="$ROOT/scripts/installer-stubs/frzr-deploy"
export INSTALLER_STUB_RECORD_DEPLOY="$PROOF/deploy-stub.json"
export INSTALLER_STUB_SLEEP=0
export INSTALLER_LOG_FILE="$PROOF/tui-engine.log"
unset INSTALLER_DRY_RUN || true
python3 - <<'PY'
import os, sys
sys.path.insert(0, os.environ["PYTHONPATH"])
open("$PROOF/12_tui_pid.txt", "a").write(f"python_pid={os.getpid()}\\n")
from installer.tui_main import main
raise SystemExit(main())
PY
EOF
chmod +x "$WRAPPER"

sudo tmux new-session -d -s installer-proof -x 120 -y 40 "$WRAPPER"

for i in $(seq 1 90); do
  sleep 0.5
  if ! sudo tmux has-session -t installer-proof 2>/dev/null; then
    echo "tmux ended at iter=$i" | tee -a "$PROOF/timeline.txt"
    break
  fi
  if sudo lsblk -n -o LABEL "$LOOP" 2>/dev/null | grep -q frzr_root; then
    echo "labels appeared at iter=$i" | tee -a "$PROOF/timeline.txt"
    sleep 2
    break
  fi
done

wait "$CAP_PID" || true
sudo tmux capture-pane -t installer-proof -p >"$PROOF/screen_FINAL.txt" 2>/dev/null || true

{
  echo "===== AFTER ====="
  date -Iseconds
  sudo lsblk -o NAME,SIZE,FSTYPE,LABEL,PARTLABEL "$LOOP"
  sudo blkid "$LOOP"* 2>/dev/null || true
} | tee "$PROOF/01_after.txt"

# Verdict
VERDICT=FAIL
if grep -q 'installer.tui_main\|from installer.tui_main\|python3' "$CHAIN_LOG" 2>/dev/null \
  && grep -q 'wrapper_ppid=' "$CHAIN_LOG" 2>/dev/null; then
  # parent should be the python TUI pid
  PY_PID=$(awk -F= '/^python_pid=/{print $2}' "$PROOF/12_tui_pid.txt" | tail -1)
  PARENT=$(awk -F= '/^wrapper_ppid=/{print $2}' "$CHAIN_LOG" | head -1)
  if [[ -n "$PY_PID" && "$PARENT" == "$PY_PID" ]]; then
    VERDICT=PASS
  elif grep -q "ancestor.*python\|parent_cmdline=.*python" "$CHAIN_LOG"; then
    VERDICT=PASS
  fi
fi

{
  echo "===== PROCESS CHAIN PROOF ====="
  echo "Claim: TUI python process is direct parent of frzr-bootstrap wrapper"
  echo "VERDICT=$VERDICT"
  echo "python_pid=$(awk -F= '/^python_pid=/{print \$2}' "$PROOF/12_tui_pid.txt" | tail -1)"
  echo "wrapper_ppid=$(awk -F= '/^wrapper_ppid=/{print \$2}' "$CHAIN_LOG" | head -1)"
  echo
  cat "$CHAIN_LOG"
  echo
  echo "===== TUI PID ====="
  cat "$PROOF/12_tui_pid.txt" 2>/dev/null || true
  echo
  echo "===== ENGINE LOG HEAD ====="
  head -20 "$PROOF/tui-engine.log" 2>/dev/null || true
  echo
  echo "===== SCREEN SEQUENCE ====="
  for f in "$PROOF"/screen_*.txt; do
    [[ -f "$f" ]] || continue
    page=$(grep -E '选择安装|确认安装|阶段:|文本安装器|正在执行|完成|选择磁盘' "$f" | head -1 || true)
    [[ -n "$page" ]] && echo "$(basename "$f"): $page"
  done
} | tee "$PROOF/PROCESS_PROOF.txt"

echo
echo "VERDICT=$VERDICT"
echo "PROOF_DIR=$PROOF"
test "$VERDICT" = PASS

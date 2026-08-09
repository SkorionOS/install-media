#!/bin/bash
# Drive REAL installer-tui inside tmux with real keystrokes against a loop disk.
# Bootstrap uses REAL frzr-bootstrap; deploy uses stub (image write faked).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SIM_DIR="${INSTALLER_SIM_DIR:-$ROOT/.sim}"
LOG_DIR="$SIM_DIR/logs"
SESSION="installer-sim-tui"
DISK_NAME="${1:?loop name without /dev/ e.g. loop3}"

mkdir -p "$LOG_DIR"

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -E env \
    "PATH=$PATH" \
    "PYTHONPATH=$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}" \
    bash "$0" "$@"
fi

export PYTHONPATH="$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}"
export TERM=xterm-256color
export INSTALLER_SIMULATION=1
export INSTALLER_SIM_AUTO=1
export INSTALLER_SIM_MODE=fresh
export INSTALLER_SIM_DISK="$DISK_NAME"
unset INSTALLER_DRY_RUN || true
export INSTALLER_FRZR_BOOTSTRAP=/usr/bin/frzr-bootstrap
export INSTALLER_ALLOW_REAL_FRZR=1
export INSTALLER_FRZR_DEPLOY="$ROOT/scripts/installer-stubs/frzr-deploy"
export INSTALLER_STUB_RECORD_DEPLOY="$LOG_DIR/tui-deploy-stub.json"
export INSTALLER_STUB_SLEEP=0
export INSTALLER_LOG_FILE="$LOG_DIR/tui.log"
export INSTALLER_REQUIRE_STUB=0

rm -f /tmp/frzr-bootstrap.lock "$INSTALLER_LOG_FILE"
tmux kill-session -t "$SESSION" 2>/dev/null || true

echo "Starting TUI in tmux (SIM_AUTO=1) session $SESSION (disk=$DISK_NAME)"
tmux new-session -d -s "$SESSION" -x 120 -y 40 \
  "cd '$ROOT' && python3 -m installer.tui_main; echo TUI_EXIT:\$?; sleep 30"

snap() { tmux capture-pane -t "$SESSION" -p > "$LOG_DIR/tmux-$1.txt" || true; }

echo "Waiting for REAL frzr-bootstrap via auto TUI (up to 10 min)..."
deadline=$((SECONDS + 600))
passed=0
while [ "$SECONDS" -lt "$deadline" ]; do
  sleep 2
  snap progress
  labels=$(lsblk -n -o LABEL "/dev/$DISK_NAME" 2>/dev/null | tr '\n' ' ')
  echo "labels: $labels"
  if echo "$labels" | grep -qiE 'frzr_root|frzr_efi'; then
    echo "[PASS] TUI auto flow produced real frzr labels on /dev/$DISK_NAME"
    lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "/dev/$DISK_NAME" | tee "$LOG_DIR/tui-lsblk-after.txt"
    passed=1
    break
  fi
  if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[FAIL] tmux session ended early"
    snap dead
    cat "$LOG_DIR/tmux-dead.txt" 2>/dev/null | head -40
    break
  fi
  # Show progress pane tip
  if [ -f "$INSTALLER_LOG_FILE" ]; then
    echo "tui.log bytes=$(wc -c < "$INSTALLER_LOG_FILE")"
  fi
done

tmux kill-session -t "$SESSION" 2>/dev/null || true

if [ "$passed" -eq 1 ]; then
  echo "[PASS] full real TUI simulation against virtual disk"
  # Show deploy stub was invoked after bootstrap
  if [ -f "$INSTALLER_STUB_RECORD_DEPLOY" ]; then
    echo "deploy stub record:"; cat "$INSTALLER_STUB_RECORD_DEPLOY"
  fi
  exit 0
fi
echo "[FAIL] timed out or failed; see $LOG_DIR/"
ls -la "$LOG_DIR"
exit 1

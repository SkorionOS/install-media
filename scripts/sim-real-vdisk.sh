#!/bin/bash
# Real end-to-end simulation against a sparse virtual disk.
# - Creates a 64GiB sparse image + losetup
# - Runs REAL /usr/bin/frzr-bootstrap (noninteractive fresh)
# - Optionally drives REAL installer-tui on a VT with uinput
# Disk writes hit only the sparse image / loop device.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SIM_DIR="${INSTALLER_SIM_DIR:-$ROOT/.sim}"
IMG="${INSTALLER_SIM_IMG:-$SIM_DIR/vdisk-64g.img}"
IMG_SIZE="${INSTALLER_SIM_SIZE:-64G}"
LOG_DIR="$SIM_DIR/logs"
mkdir -p "$SIM_DIR" "$LOG_DIR"

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "Re-executing with sudo..."
    exec sudo -E env \
      "PATH=$PATH" \
      "HOME=$HOME" \
      "INSTALLER_SIM_DIR=$SIM_DIR" \
      "INSTALLER_SIM_IMG=$IMG" \
      "INSTALLER_SIM_SIZE=$IMG_SIZE" \
      "PYTHONPATH=$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}" \
      bash "$0" "$@"
  fi
}

cleanup_mounts() {
  local loop="$1"
  # Unmount anything under /tmp/frzr_root that belongs to this run
  if mountpoint -q /tmp/frzr_root/boot/efi 2>/dev/null; then umount /tmp/frzr_root/boot/efi || umount -l /tmp/frzr_root/boot/efi || true; fi
  if mountpoint -q /tmp/frzr_root/boot 2>/dev/null; then umount /tmp/frzr_root/boot || umount -l /tmp/frzr_root/boot || true; fi
  if mountpoint -q /tmp/frzr_root 2>/dev/null; then umount /tmp/frzr_root || umount -l /tmp/frzr_root || true; fi
  # Also unmount any loop partitions still mounted
  lsblk -ln -o NAME,MOUNTPOINT "$loop" 2>/dev/null | while read -r name mnt; do
    [ -n "$mnt" ] || continue
    umount "$mnt" 2>/dev/null || umount -l "$mnt" 2>/dev/null || true
  done
}

setup_vdisk() {
  echo "=== Creating sparse virtual disk: $IMG ($IMG_SIZE) ==="
  mkdir -p "$(dirname "$IMG")"
  if [ ! -f "$IMG" ]; then
    truncate -s "$IMG_SIZE" "$IMG"
  else
    # Recreate for a clean fresh install each run
    rm -f "$IMG"
    truncate -s "$IMG_SIZE" "$IMG"
  fi
  # Detach any existing association for this image
  local existing
  existing=$(losetup -j "$IMG" -O NAME -n 2>/dev/null || true)
  if [ -n "$existing" ]; then
    cleanup_mounts "$existing" || true
    losetup -d "$existing" || true
  fi
  LOOP=$(losetup -f --show -P "$IMG")
  echo "LOOP=$LOOP"
  lsblk "$LOOP"
  echo "$LOOP" > "$SIM_DIR/loop.dev"
}

assert_bootstrap_result() {
  local loop="$1"
  echo "=== Asserting partitions on $loop ==="
  lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "$loop" | tee "$LOG_DIR/lsblk-after.txt"
  # Expect frzr labels somewhere on children
  local labels
  labels=$(lsblk -n -o LABEL "$loop" | tr '\n' ' ')
  echo "Labels: $labels"
  if ! lsblk -n -o LABEL "$loop" | grep -qiE 'frzr|efi|boot'; then
    echo "[FAIL] expected frzr/efi/boot labels on virtual disk"
    return 1
  fi
  echo "[PASS] virtual disk has installer-created labels"
}

run_real_bootstrap() {
  local loop="$1"
  local disk_name="${loop#/dev/}"
  echo "=== REAL frzr-bootstrap fresh on $loop ==="
  export FRZR_NONINTERACTIVE=1
  set +e
  /usr/bin/frzr-bootstrap gamer "$loop" fresh 2>&1 | tee "$LOG_DIR/frzr-bootstrap.log"
  local rc=${PIPESTATUS[0]}
  set -e
  echo "frzr-bootstrap exit=$rc"
  if [ "$rc" -ne 0 ]; then
    echo "[FAIL] real frzr-bootstrap failed"
    return "$rc"
  fi
  assert_bootstrap_result "$loop"
}

run_engine_against_loop() {
  local loop="$1"
  local disk_name="${loop#/dev/}"
  echo "=== InstallEngine -> REAL frzr-bootstrap on $loop ==="
  export PYTHONPATH="$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}"
  unset INSTALLER_DRY_RUN || true
  export INSTALLER_FRZR_BOOTSTRAP=/usr/bin/frzr-bootstrap
  export INSTALLER_ALLOW_REAL_FRZR=1
  # Deploy still stubbed (full image download/write); bootstrap is real.
  export INSTALLER_FRZR_DEPLOY="$ROOT/scripts/installer-stubs/frzr-deploy"
  export INSTALLER_STUB_SLEEP=0
  export INSTALLER_STUB_RECORD_DEPLOY="$LOG_DIR/deploy-stub.json"

  python3 - <<PY
from installer.engine import InstallPlan, BootstrapService, DeployService

plan = InstallPlan(disk="$disk_name", mode="fresh", source="online",
                   channel="stable", desktop="gnome", nvidia=False)
print("Running bootstrap via engine...")
res = BootstrapService(on_event=lambda e: print(f"[{e.kind.value}] {e.message[:200] if e.message else ''}", flush=True)).run(
    plan, log_file="$LOG_DIR/engine-bootstrap.log"
)
print("bootstrap returncode", res.returncode)
raise SystemExit(res.returncode)
PY
  assert_bootstrap_result "$loop"

  echo "=== Deploy via stub (image write faked) ==="
  python3 - <<PY
from installer.engine import InstallPlan, DeployService
plan = InstallPlan(disk="$disk_name", mode="fresh", source="online",
                   channel="stable", desktop="gnome", nvidia=False)
res = DeployService(on_event=lambda e: print(f"[{e.kind.value}] {e.message[:200] if e.message else ''}", flush=True)).run(
    plan, log_file="$LOG_DIR/engine-deploy.log"
)
print("deploy returncode", res.returncode)
raise SystemExit(0 if res.returncode == 0 else res.returncode)
PY
}

run_tui_on_vt() {
  local loop="$1"
  local disk_name="${loop#/dev/}"
  local ttyn="${INSTALLER_SIM_TTY:-15}"
  echo "=== REAL installer-tui on VT$ttyn selecting $disk_name ==="
  export PYTHONPATH="$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}"
  export INSTALLER_SIMULATION=1
  export INSTALLER_SIM_DISK="$disk_name"
  unset INSTALLER_DRY_RUN || true
  export INSTALLER_FRZR_BOOTSTRAP=/usr/bin/frzr-bootstrap
  export INSTALLER_ALLOW_REAL_FRZR=1
  export INSTALLER_FRZR_DEPLOY="$ROOT/scripts/installer-stubs/frzr-deploy"
  export INSTALLER_STUB_RECORD_DEPLOY="$LOG_DIR/tui-deploy-stub.json"
  export INSTALLER_STUB_SLEEP=0
  export INSTALLER_LOG_FILE="$LOG_DIR/tui.log"
  export TERM=linux

  # Reset disk for a clean TUI run
  cleanup_mounts "$loop" || true
  wipefs -a "$loop" 2>/dev/null || true
  # recreate sparse association
  losetup -d "$loop" 2>/dev/null || true
  truncate -s 0 "$IMG" 2>/dev/null || true
  truncate -s "$IMG_SIZE" "$IMG"
  LOOP=$(losetup -f --show -P "$IMG")
  disk_name="${LOOP#/dev/}"
  export INSTALLER_SIM_DISK="$disk_name"
  echo "Fresh LOOP=$LOOP"

  bash "$ROOT/scripts/sim-drive-tui-tmux.sh" "$disk_name" 2>&1 | tee "$LOG_DIR/tui-drive.log"
}

usage() {
  cat <<EOF
Usage: $0 [--bootstrap-only|--engine|--tui|--all]
  --bootstrap-only  real frzr-bootstrap on vdisk
  --engine          InstallEngine -> real bootstrap + stub deploy
  --tui             real Textual TUI on VT + uinput + real bootstrap
  --all             bootstrap-only then engine (default)
EOF
}

main() {
  need_root "$@"
  local mode="${1:---all}"
  setup_vdisk
  LOOP=$(cat "$SIM_DIR/loop.dev")

  case "$mode" in
    --bootstrap-only)
      run_real_bootstrap "$LOOP"
      ;;
    --engine)
      # clean disk first
      wipefs -a "$LOOP" 2>/dev/null || true
      run_engine_against_loop "$LOOP"
      ;;
    --tui)
      run_tui_on_vt "$LOOP"
      ;;
    --all)
      run_real_bootstrap "$LOOP"
      echo
      # recreate clean disk for engine path
      cleanup_mounts "$LOOP" || true
      losetup -d "$LOOP" || true
      rm -f "$IMG"
      truncate -s "$IMG_SIZE" "$IMG"
      LOOP=$(losetup -f --show -P "$IMG")
      echo "$LOOP" > "$SIM_DIR/loop.dev"
      run_engine_against_loop "$LOOP"
      ;;
    -h|--help)
      usage
      ;;
    *)
      usage; exit 2
      ;;
  esac

  echo
  echo "=== SIMULATION COMPLETE ==="
  echo "Image: $IMG"
  echo "Loop:  $(cat "$SIM_DIR/loop.dev")"
  echo "Logs:  $LOG_DIR"
}

main "$@"

#!/usr/bin/env bash
# Agent-driven TUI full verify on sparse vdisk:
#   real screenshots each step + real frzr-bootstrap + real frzr-deploy (download/write)
# Runs inside mount namespace so host /frzr_root is never written.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${INSTALLER_FULL_OUT:-$ROOT/.sim/tui-full-verify}"
IMG="$OUT/vdisk-64g.img"
IMG_SIZE="${INSTALLER_SIM_SIZE:-64G}"
SHOT="$OUT/shots"
LOG="$OUT/logs"
mkdir -p "$OUT" "$SHOT" "$LOG"

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    exec sudo -E env \
      "PATH=$PATH" \
      "HOME=$HOME" \
      "INSTALLER_FULL_OUT=$OUT" \
      "INSTALLER_SIM_SIZE=$IMG_SIZE" \
      "PYTHONPATH=$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}" \
      bash "$0" "$@"
  fi
}

need_root "$@"

echo "=== TUI FULL VDISK VERIFY ===" | tee "$OUT/RESULT.txt"
date -Iseconds | tee -a "$OUT/RESULT.txt"

# Drop previous association
if [ -f "$IMG" ]; then
  for L in $(losetup -j "$IMG" -O NAME -n 2>/dev/null || true); do
    umount /tmp/frzr_root/boot 2>/dev/null || true
    umount /tmp/frzr_root 2>/dev/null || true
    losetup -d "$L" 2>/dev/null || true
  done
fi
rm -f "$IMG"
rm -f "$SHOT"/* 2>/dev/null || true
truncate -s "$IMG_SIZE" "$IMG"
LOOP=$(losetup -f --show -P "$IMG")
DISK="${LOOP#/dev/}"
echo "LOOP=$LOOP DISK=$DISK" | tee -a "$OUT/RESULT.txt"
echo "$LOOP" >"$OUT/loop.txt"

HOST_BEFORE=$(ls /frzr_root/deployments 2>/dev/null | sort | tr '\n' ' ' || true)
echo "HOST_DEPLOYMENTS_BEFORE=$HOST_BEFORE" | tee -a "$OUT/RESULT.txt"

umount /tmp/frzr_root/boot 2>/dev/null || true
umount /tmp/frzr_root 2>/dev/null || true

# Agent drives TUI (SIM_AUTO) inside mount NS; Textual exports shots to SHOT.
unshare -m bash -c "
set -euo pipefail
mount --make-rprivate /
umount -l /frzr_root/boot 2>/dev/null || true
umount -l /frzr_root 2>/dev/null || true

export PYTHONPATH='$ROOT/skorionos/airootfs/usr/local/lib'
export TERM=xterm-256color
export COLORTERM=truecolor
export INSTALLER_SIMULATION=1
export INSTALLER_SIM_DISK='$DISK'
export INSTALLER_SIM_AUTO=1
export INSTALLER_SIM_AUTO_DELAY=0.55
export INSTALLER_SIM_MODE=fresh
export INSTALLER_SHOT_DIR='$SHOT'
export INSTALLER_FRZR_BOOTSTRAP=/usr/bin/frzr-bootstrap
export INSTALLER_FRZR_DEPLOY=/usr/bin/frzr-deploy
export INSTALLER_ALLOW_REAL_FRZR=1
export INSTALLER_LOG_FILE='$LOG/tui-engine.log'
unset INSTALLER_DRY_RUN || true
unset INSTALLER_REQUIRE_STUB || true
unset INSTALLER_DEV || true

cd '$ROOT'
# script gives Textual a PTY
script -q -f -c 'python3 -m installer.tui_main' '$LOG/tui.typescript'
" 2>&1 | tee "$LOG/tui_ns.log"

echo "tui_ns_exit=$?" | tee -a "$OUT/RESULT.txt"

# Resolve loop partitions
ROOT_PART=$(blkid -t LABEL=frzr_root -o device | while read -r d; do
  case "$(lsblk -no PKNAME "$d" 2>/dev/null)" in
    "$DISK") echo "$d"; break ;;
  esac
done)
EFI_PART=$(blkid -t LABEL=frzr_efi -o device | while read -r d; do
  case "$(lsblk -no PKNAME "$d" 2>/dev/null)" in
    "$DISK") echo "$d"; break ;;
  esac
done)
[ -n "$ROOT_PART" ] || ROOT_PART="${LOOP}p2"
[ -n "$EFI_PART" ] || EFI_PART="${LOOP}p1"
echo "ROOT_PART=$ROOT_PART EFI_PART=$EFI_PART" | tee -a "$OUT/RESULT.txt"

MNT="$OUT/mnt"
mkdir -p "$MNT/root" "$MNT/boot"
umount "$MNT/boot" 2>/dev/null || true
umount "$MNT/root" 2>/dev/null || true
mount -o ro "$ROOT_PART" "$MNT/root"
mount -o ro "$EFI_PART" "$MNT/boot"

{
  echo "===== shots ====="
  ls -la "$SHOT"
  echo "===== deployments ====="
  ls -la "$MNT/root/deployments" 2>/dev/null || true
  btrfs subvolume list "$MNT/root" 2>/dev/null || true
  echo "===== source ====="
  cat "$MNT/root/source" 2>/dev/null || true
  echo "===== frzr.conf ====="
  cat "$MNT/boot/loader/entries/frzr.conf" 2>/dev/null || true
  echo "===== kernels ====="
  find "$MNT/boot" -name 'vmlinuz*' -ls 2>/dev/null | head
  du -sh "$MNT/root/deployments"/* 2>/dev/null | head
} | tee "$LOG/assert.txt"

HOST_AFTER=$(ls /frzr_root/deployments 2>/dev/null | sort | tr '\n' ' ' || true)
echo "HOST_DEPLOYMENTS_AFTER=$HOST_AFTER" | tee -a "$OUT/RESULT.txt"

FAIL=0
SHOT_PNG=$(ls "$SHOT"/*.png 2>/dev/null | wc -l)
SHOT_SVG=$(ls "$SHOT"/*.svg 2>/dev/null | wc -l)
echo "SHOT_PNG=$SHOT_PNG SHOT_SVG=$SHOT_SVG" | tee -a "$OUT/RESULT.txt"
if [ "$SHOT_PNG" -lt 6 ] && [ "$SHOT_SVG" -lt 6 ]; then
  echo "[FAIL] too few UI screenshots" | tee -a "$OUT/RESULT.txt"
  FAIL=1
else
  echo "[PASS] UI screenshots present" | tee -a "$OUT/RESULT.txt"
fi
if ! ls "$MNT/root/deployments" 2>/dev/null | grep -qiE 'skorionos|chimeraos'; then
  echo "[FAIL] no deployment on loop (UI path did not write system)" | tee -a "$OUT/RESULT.txt"
  FAIL=1
else
  echo "[PASS] deployment written on loop" | tee -a "$OUT/RESULT.txt"
fi
if [ ! -f "$MNT/boot/loader/entries/frzr.conf" ]; then
  echo "[FAIL] missing frzr.conf" | tee -a "$OUT/RESULT.txt"
  FAIL=1
fi
if [ "$HOST_BEFORE" != "$HOST_AFTER" ]; then
  echo "[FAIL] host deployments changed" | tee -a "$OUT/RESULT.txt"
  FAIL=1
else
  echo "[PASS] host unchanged" | tee -a "$OUT/RESULT.txt"
fi

umount "$MNT/boot" 2>/dev/null || true
umount "$MNT/root" 2>/dev/null || true

if [ "$FAIL" -eq 0 ]; then
  echo "VERDICT=PASS" | tee -a "$OUT/RESULT.txt"
else
  echo "VERDICT=FAIL" | tee -a "$OUT/RESULT.txt"
fi
exit "$FAIL"

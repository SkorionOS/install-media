#!/usr/bin/env bash
# Full real verification on a sparse virtual disk:
#   InstallEngine -> real frzr-bootstrap -> real frzr-deploy (download + write)
#
# Host already has /frzr_root mounted (live system). Deploy prefers that path,
# so we run deploy inside `unshare -m` with a private mount namespace and bind
# the LOOP partitions there — never write to the host OS disk.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# All artifacts stay under .sim/ (gitignored) — never litter repo root.
OUT="${INSTALLER_FULL_OUT:-$ROOT/.sim/full-verify}"
IMG="$OUT/vdisk-64g.img"
IMG_SIZE="${INSTALLER_SIM_SIZE:-64G}"
LOG="$OUT/logs"
mkdir -p "$OUT" "$LOG"

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

cleanup_loop() {
  local loop="${1:-}"
  umount /tmp/frzr_root/boot 2>/dev/null || true
  umount /tmp/frzr_root 2>/dev/null || true
  if [ -n "$loop" ]; then
    lsblk -ln -o NAME,MOUNTPOINT "$loop" 2>/dev/null | while read -r name mnt; do
      [ -n "${mnt:-}" ] || continue
      umount "$mnt" 2>/dev/null || umount -l "$mnt" 2>/dev/null || true
    done
    losetup -d "$loop" 2>/dev/null || true
  fi
}

need_root "$@"

echo "=== FULL VDISK VERIFY ===" | tee "$OUT/RESULT.txt"
date -Iseconds | tee -a "$OUT/RESULT.txt"

# Detach previous image associations
if [ -f "$IMG" ]; then
  for L in $(losetup -j "$IMG" -O NAME -n 2>/dev/null || true); do
    cleanup_loop "$L"
  done
fi
rm -f "$IMG"
truncate -s "$IMG_SIZE" "$IMG"
LOOP=$(losetup -f --show -P "$IMG")
DISK="${LOOP#/dev/}"
echo "LOOP=$LOOP DISK=$DISK IMG=$IMG" | tee -a "$OUT/RESULT.txt"
echo "$LOOP" >"$OUT/loop.txt"

# Record host frzr_root major:minor so we can prove we did not write there
HOST_ROOT_SRC=$(findmnt -n -o SOURCE /frzr_root 2>/dev/null || true)
HOST_ROOT_UUID=$(findmnt -n -o UUID /frzr_root 2>/dev/null || true)
echo "HOST_FRZR_ROOT_SOURCE=$HOST_ROOT_SRC UUID=$HOST_ROOT_UUID" | tee -a "$OUT/RESULT.txt"
BEFORE_HOST_DEPLOY=$(ls /frzr_root/deployments 2>/dev/null | sort | tr '\n' ' ' || true)
echo "HOST_DEPLOYMENTS_BEFORE=$BEFORE_HOST_DEPLOY" | tee -a "$OUT/RESULT.txt"

{
  echo "===== BEFORE ====="
  lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "$LOOP"
} | tee "$LOG/00_before.txt"

# --- 1) REAL bootstrap via InstallEngine ---
export PYTHONPATH="$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}"
unset INSTALLER_DRY_RUN || true
unset INSTALLER_FRZR_DEPLOY || true
unset INSTALLER_REQUIRE_STUB || true
export INSTALLER_FRZR_BOOTSTRAP=/usr/bin/frzr-bootstrap
export INSTALLER_ALLOW_REAL_FRZR=1
export FRZR_NONINTERACTIVE=1

echo "=== ENGINE bootstrap (real) ===" | tee -a "$OUT/RESULT.txt"
python3 - <<PY 2>&1 | tee "$LOG/01_engine_bootstrap.log"
from installer.engine import InstallPlan, BootstrapService, ProgressEvent

def on_event(e):
    msg = (e.message or "")[:300]
    print(f"[{e.kind.value}] {msg}", flush=True)

plan = InstallPlan(
    disk="$DISK", mode="fresh", source="online",
    channel="stable", desktop="gnome", nvidia=False,
)
res = BootstrapService(on_event=on_event).run(plan, log_file="$LOG/01_engine_bootstrap.log")
print("bootstrap_returncode", res.returncode, flush=True)
raise SystemExit(res.returncode)
PY

{
  echo "===== AFTER BOOTSTRAP ====="
  lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "$LOOP"
  blkid "${LOOP}"* || true
} | tee "$LOG/02_after_bootstrap.txt"

# Resolve partition nodes (prefer blkid — lsblk can omit FAT LABEL briefly)
ROOT_PART=$(blkid -t LABEL=frzr_root -o device | while read -r d; do
  case "$(lsblk -no PKNAME "$d" 2>/dev/null)" in
    "${LOOP#/dev/}") echo "$d"; break ;;
  esac
done)
EFI_PART=$(blkid -t LABEL=frzr_efi -o device | while read -r d; do
  case "$(lsblk -no PKNAME "$d" 2>/dev/null)" in
    "${LOOP#/dev/}") echo "$d"; break ;;
  esac
done)
# Fallback: partition order from bootstrap fresh layout
if [ -z "$ROOT_PART" ] || [ -z "$EFI_PART" ]; then
  if [ -b "${LOOP}p1" ] && [ -b "${LOOP}p2" ]; then
    EFI_PART="${LOOP}p1"
    ROOT_PART="${LOOP}p2"
  elif [ -b "${LOOP}p1" ]; then
    # non-partitionable naming
    EFI_PART=$(lsblk -rno PATH,FSTYPE "$LOOP" | awk '$2=="vfat"{print $1; exit}')
    ROOT_PART=$(lsblk -rno PATH,FSTYPE "$LOOP" | awk '$2=="btrfs"{print $1; exit}')
  fi
fi
if [ -z "$ROOT_PART" ] || [ -z "$EFI_PART" ]; then
  echo "[FAIL] bootstrap did not create frzr_root/frzr_efi on loop" | tee -a "$OUT/RESULT.txt"
  blkid "$LOOP"* 2>/dev/null | tee -a "$OUT/RESULT.txt" || true
  exit 1
fi
echo "ROOT_PART=$ROOT_PART EFI_PART=$EFI_PART" | tee -a "$OUT/RESULT.txt"
LOOP_ROOT_UUID=$(blkid -s UUID -o value "$ROOT_PART")
echo "LOOP_ROOT_UUID=$LOOP_ROOT_UUID" | tee -a "$OUT/RESULT.txt"

# Unmount bootstrap leftovers on host NS (they use /tmp/frzr_root)
umount /tmp/frzr_root/boot 2>/dev/null || true
umount /tmp/frzr_root 2>/dev/null || true

# --- 2) REAL deploy (download + write) in private mount namespace ---
echo "=== ENGINE deploy (real download+write) in mount NS ===" | tee -a "$OUT/RESULT.txt"
# shellcheck disable=SC2094
unshare -m bash -c "
set -euo pipefail
mount --make-rprivate /
# Detach host frzr_root inside this namespace only
umount -l /frzr_root/boot 2>/dev/null || true
umount -l /frzr_root 2>/dev/null || true
# Prefer /frzr_root path that deploy uses first
mkdir -p /frzr_root/boot
mount -t btrfs -o nodatacow '$ROOT_PART' /frzr_root
mount -t vfat '$EFI_PART' /frzr_root/boot
echo 'NS_MOUNTS:' \$(findmnt -n -o SOURCE,TARGET /frzr_root /frzr_root/boot)
echo 'NS_ROOT_UUID=' \$(findmnt -n -o UUID /frzr_root)
# Prove NS root is the LOOP, not host
NS_UUID=\$(findmnt -n -o UUID /frzr_root)
if [ \"\$NS_UUID\" != '$LOOP_ROOT_UUID' ]; then
  echo '[FAIL] mount NS /frzr_root UUID != loop UUID' >&2
  exit 2
fi
export PYTHONPATH='$ROOT/skorionos/airootfs/usr/local/lib'
export INSTALLER_ALLOW_REAL_FRZR=1
export INSTALLER_FRZR_BOOTSTRAP=/usr/bin/frzr-bootstrap
export INSTALLER_FRZR_DEPLOY=/usr/bin/frzr-deploy
unset INSTALLER_DRY_RUN || true
unset INSTALLER_REQUIRE_STUB || true
python3 - <<'PY'
from installer.engine import InstallPlan, DeployService

def on_event(e):
    msg = (e.message or '')[:400]
    print(f'[{e.kind.value}] {msg}', flush=True)

plan = InstallPlan(
    disk='$DISK', mode='fresh', source='online',
    channel='stable', desktop='gnome', nvidia=False,
)
res = DeployService(on_event=on_event).run(plan, log_file='$LOG/03_engine_deploy.log')
print('deploy_returncode', res.returncode, flush=True)
raise SystemExit(res.returncode)
PY
" 2>&1 | tee "$LOG/03_deploy_ns.log"

echo "deploy_ns_exit=$?" | tee -a "$OUT/RESULT.txt"

# --- 3) Assert loop contents (mount read-only in host NS at a private path) ---
MNT="$OUT/mnt"
mkdir -p "$MNT/root" "$MNT/boot"
umount "$MNT/boot" 2>/dev/null || true
umount "$MNT/root" 2>/dev/null || true
mount -o ro "$ROOT_PART" "$MNT/root"
mount -o ro "$EFI_PART" "$MNT/boot"

{
  echo "===== LOOP ROOT TREE (top) ====="
  ls -la "$MNT/root"
  echo "===== deployments ====="
  ls -la "$MNT/root/deployments" 2>/dev/null || echo '(no deployments dir)'
  btrfs subvolume list "$MNT/root" 2>/dev/null || true
  echo "===== source file ====="
  cat "$MNT/root/source" 2>/dev/null || true
  echo "===== boot loader ====="
  ls -la "$MNT/boot/loader/entries" 2>/dev/null || true
  cat "$MNT/boot/loader/entries/frzr.conf" 2>/dev/null || true
  echo "===== boot deployment kernels ====="
  find "$MNT/boot" -maxdepth 2 -type f \( -name 'vmlinuz*' -o -name 'initramfs*' \) -ls 2>/dev/null | head -40
  echo "===== du ====="
  du -sh "$MNT/root/deployments"/* 2>/dev/null | head -20
  du -sh "$MNT/boot"/* 2>/dev/null | head -20
} | tee "$LOG/04_loop_assert.txt"

AFTER_HOST_DEPLOY=$(ls /frzr_root/deployments 2>/dev/null | sort | tr '\n' ' ' || true)
echo "HOST_DEPLOYMENTS_AFTER=$AFTER_HOST_DEPLOY" | tee -a "$OUT/RESULT.txt"

FAIL=0
if ! ls "$MNT/root/deployments" 2>/dev/null | grep -qiE 'skorionos|chimeraos'; then
  echo "[FAIL] no skorionos/chimeraos deployment subvol on LOOP" | tee -a "$OUT/RESULT.txt"
  FAIL=1
fi
if [ ! -f "$MNT/boot/loader/entries/frzr.conf" ]; then
  echo "[FAIL] missing frzr.conf on LOOP EFI" | tee -a "$OUT/RESULT.txt"
  FAIL=1
fi
if ! find "$MNT/boot" -name 'vmlinuz*' | grep -q .; then
  echo "[FAIL] missing vmlinuz on LOOP EFI" | tee -a "$OUT/RESULT.txt"
  FAIL=1
fi
if [ "$BEFORE_HOST_DEPLOY" != "$AFTER_HOST_DEPLOY" ]; then
  echo "[FAIL] HOST /frzr_root/deployments changed — deploy hit the live system!" | tee -a "$OUT/RESULT.txt"
  FAIL=1
else
  echo "[PASS] host deployments unchanged" | tee -a "$OUT/RESULT.txt"
fi
# Download evidence in deploy log
if rg -q 'download|Downloading|curl|skosys|进度|%|BASE_URL|Executing' "$LOG/03_deploy_ns.log" "$LOG/03_engine_deploy.log" 2>/dev/null; then
  echo "[PASS] deploy log shows download/write activity" | tee -a "$OUT/RESULT.txt"
else
  echo "[WARN] could not pattern-match download lines; inspect logs" | tee -a "$OUT/RESULT.txt"
fi

umount "$MNT/boot" 2>/dev/null || true
umount "$MNT/root" 2>/dev/null || true

if [ "$FAIL" -eq 0 ]; then
  echo "VERDICT=PASS" | tee -a "$OUT/RESULT.txt"
else
  echo "VERDICT=FAIL" | tee -a "$OUT/RESULT.txt"
fi
echo "OUT=$OUT"
exit "$FAIL"

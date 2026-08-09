#!/bin/bash
# Dry-run / stub bootstrap via InstallEngine (no ISO rebuild, no disk writes).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}"
export INSTALLER_DRY_RUN="${INSTALLER_DRY_RUN:-0}"
export INSTALLER_FRZR_BOOTSTRAP="$ROOT/scripts/installer-stubs/frzr-bootstrap"
export INSTALLER_STUB_RECORD="${INSTALLER_STUB_RECORD:-/tmp/installer-stub-bootstrap.json}"
export INSTALLER_REQUIRE_STUB=1

MODE="${1:-fresh}"
DISK="${2:-nvme0n1}"
DUAL_OP="${3:-}"
SHRINK_PART="${4:-}"
SHRINK_SIZE="${5:-}"

rm -f "$INSTALLER_STUB_RECORD"

python3 - <<PY
from installer.engine import InstallPlan, BootstrapService

plan = InstallPlan(disk="$DISK", mode="$MODE")
if plan.mode == "dual":
    plan.dual_op = "${DUAL_OP:-auto}" or "auto"
    if plan.dual_op == "shrink":
        plan.shrink_partition = "$SHRINK_PART" or "/dev/${DISK}p3"
        plan.shrink_size_gb = int("${SHRINK_SIZE:-60}" or "60")
    elif plan.dual_op == "delete":
        plan.delete_partition = "$SHRINK_PART" or "/dev/${DISK}p3"

events = []
svc = BootstrapService(on_event=lambda e: (events.append(e), print(f"[{e.kind.value}] {e.message}", end="" if e.message.endswith("\n") else "\n")))
result = svc.run(plan, log_file="/tmp/installer-engine-bootstrap.log")
print("returncode=", result.returncode, "dry_run=", result.dry_run)
print("argv=", result.argv)
print("env_overlay=", result.env_overlay)
raise SystemExit(0 if result.returncode == 0 else result.returncode)
PY

if [ -f "$INSTALLER_STUB_RECORD" ]; then
  echo "--- stub record ---"
  cat "$INSTALLER_STUB_RECORD"
else
  echo "--- stub record: (none; dry-run does not invoke stub) ---"
fi

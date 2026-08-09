#!/bin/bash
# Headless full bootstrap+deploy via engine + stubs (CI-friendly).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}"
export INSTALLER_FRZR_BOOTSTRAP="$ROOT/scripts/installer-stubs/frzr-bootstrap"
export INSTALLER_FRZR_DEPLOY="$ROOT/scripts/installer-stubs/frzr-deploy"
export INSTALLER_STUB_RECORD=/tmp/installer-stub-bootstrap.json
export INSTALLER_STUB_RECORD_DEPLOY=/tmp/installer-stub-deploy.json
export INSTALLER_STUB_SLEEP=0
export INSTALLER_REQUIRE_STUB=1
rm -f "$INSTALLER_STUB_RECORD" "$INSTALLER_STUB_RECORD_DEPLOY"

python3 - <<'PY'
from installer.engine import InstallPlan, BootstrapService, DeployService

plan = InstallPlan(
    disk="nvme0n1",
    mode="dual",
    dual_op="shrink",
    shrink_partition="/dev/nvme0n1p3",
    shrink_size_gb=60,
    source="online",
    channel="stable",
    desktop="gnome",
    nvidia=True,
)
print("bootstrap...")
br = BootstrapService(on_event=lambda e: print(e.kind.value, e.message[:120] if e.message else "")).run(
    plan, log_file="/tmp/installer-engine-full.log"
)
assert br.returncode == 0, br
print("deploy...")
dr = DeployService(on_event=lambda e: print(e.kind.value, e.message[:120] if e.message else "")).run(
    plan, log_file="/tmp/installer-engine-full.log"
)
assert dr.returncode == 0, dr
print("OK full engine path")
PY

echo "--- bootstrap record ---"
cat /tmp/installer-stub-bootstrap.json
echo "--- deploy record ---"
cat /tmp/installer-stub-deploy.json

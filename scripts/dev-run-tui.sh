#!/bin/bash
# Launch Textual TUI against stubs (no ISO, no real disks).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}"
unset NO_COLOR
export TERM="${TERM:-xterm-256color}"
export COLORTERM="${COLORTERM:-truecolor}"
export INSTALLER_DEV=1
export INSTALLER_DRY_RUN="${INSTALLER_DRY_RUN:-0}"
export INSTALLER_FRZR_BOOTSTRAP="$ROOT/scripts/installer-stubs/frzr-bootstrap"
export INSTALLER_FRZR_DEPLOY="$ROOT/scripts/installer-stubs/frzr-deploy"
export INSTALLER_STUB_SLEEP="${INSTALLER_STUB_SLEEP:-0.05}"
export INSTALLER_REQUIRE_STUB=1
export INSTALLER_LOG_FILE="${INSTALLER_LOG_FILE:-/tmp/frzr-tui.log}"
chmod +x "$ROOT/skorionos/airootfs/usr/local/bin/installer-tui" 2>/dev/null || true
exec python3 -m installer.tui_main

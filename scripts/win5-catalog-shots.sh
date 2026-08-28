#!/usr/bin/env bash
# Run remaining coverage_catalog visual cases on this machine (Win5).
# VT = openvt + fb0. GUI = nested gamescope (not DRM). Simulation + stubs only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${INSTALLER_PYTHON:-python3}"
export INSTALLER_VT_TTY="${INSTALLER_VT_TTY:-3}"
export PYTHONPATH="$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}"

clear_case() {
  unset INSTALLER_SIM_MODE INSTALLER_SIM_DUAL INSTALLER_SIM_FRZR INSTALLER_SIM_DISK_GATE \
    INSTALLER_SIM_NAV INSTALLER_SIM_NAV_AT INSTALLER_STUB_EXIT INSTALLER_STUB_DEPLOY_EXIT \
    INSTALLER_SIM_ADVANCED INSTALLER_SIM_ONLINE INSTALLER_SIM_WIFI INSTALLER_SIM_CONFIRM_BACK \
    INSTALLER_SIM_DESKTOP INSTALLER_SIM_NVIDIA INSTALLER_SIM_LOCAL INSTALLER_SIM_SOURCE \
    INSTALLER_SIM_WIFI_SSID INSTALLER_GAMESCOPE_BACKEND INSTALLER_VT_OUT INSTALLER_WINDOW_OUT \
    INSTALLER_SIM_NAV || true
}

stamp() { date +%H%M%S; }

log() { echo "=== $* ==="; }

vt_case() {
  local name="$1"; shift
  clear_case
  export "$@"
  export INSTALLER_VT_OUT="$ROOT/.sim/vt-${name}-$(stamp)"
  log "VT $name → $INSTALLER_VT_OUT"
  if ! "$PY" "$ROOT/scripts/agent-vt-fb-shots.py"; then
    echo "FAIL VT $name" | tee -a "$ROOT/.sim/catalog-run.log"
    return 1
  fi
}

gui_case() {
  local name="$1"; shift
  clear_case
  export "$@"
  export INSTALLER_WINDOW_OUT="$ROOT/.sim/gui-${name}-$(stamp)"
  log "GUI $name → $INSTALLER_WINDOW_OUT"
  if ! "$PY" "$ROOT/scripts/agent-gui-window-shots.py"; then
    echo "FAIL GUI $name" | tee -a "$ROOT/.sim/catalog-run.log"
    return 1
  fi
}

mkdir -p "$ROOT/.sim"
: > "$ROOT/.sim/catalog-run.log"
fails=0
MODE="${1:-all}"

if [[ "$MODE" == all || "$MODE" == vt ]]; then
  vt_case fresh_local INSTALLER_SIM_MODE=fresh INSTALLER_SIM_ONLINE=1 INSTALLER_SIM_LOCAL=1 INSTALLER_SIM_SOURCE=local || fails=$((fails + 1))
  vt_case offline INSTALLER_SIM_MODE=fresh INSTALLER_SIM_ONLINE=0 INSTALLER_SIM_LOCAL=0 || fails=$((fails + 1))
  vt_case dual_delete INSTALLER_SIM_MODE=dual INSTALLER_SIM_DUAL=delete INSTALLER_SIM_ONLINE=1 || fails=$((fails + 1))
  vt_case no_shrink INSTALLER_SIM_MODE=dual INSTALLER_SIM_DUAL=no_shrink INSTALLER_SIM_ONLINE=1 || fails=$((fails + 1))
  vt_case ext_incomplete INSTALLER_SIM_DISK_GATE=external INSTALLER_SIM_FRZR=incomplete INSTALLER_SIM_ONLINE=1 || fails=$((fails + 1))
  vt_case deploy_fail INSTALLER_SIM_MODE=fresh INSTALLER_SIM_ONLINE=1 INSTALLER_STUB_DEPLOY_EXIT=1 || fails=$((fails + 1))
  vt_case wifi INSTALLER_SIM_WIFI=1 INSTALLER_SIM_ONLINE=0 INSTALLER_SIM_LOCAL=0 || fails=$((fails + 1))
  vt_case kde_nv INSTALLER_SIM_MODE=fresh INSTALLER_SIM_ONLINE=1 INSTALLER_SIM_LOCAL=0 INSTALLER_SIM_DESKTOP=kde INSTALLER_SIM_NVIDIA=1 || fails=$((fails + 1))
  vt_case confirm_back INSTALLER_SIM_ONLINE=1 INSTALLER_SIM_CONFIRM_BACK=1 || fails=$((fails + 1))
fi

if [[ "$MODE" == all ]]; then
  gui_case external INSTALLER_SIM_DISK_GATE=external INSTALLER_SIM_ONLINE=1 || fails=$((fails + 1))
  gui_case dual_auto INSTALLER_SIM_MODE=dual INSTALLER_SIM_DUAL=auto INSTALLER_SIM_ONLINE=1 || fails=$((fails + 1))
  gui_case cancel INSTALLER_SIM_ONLINE=1 INSTALLER_SIM_NAV=exit INSTALLER_SIM_NAV_AT=mode || fails=$((fails + 1))
  gui_case advanced INSTALLER_SIM_MODE=fresh INSTALLER_SIM_ONLINE=1 INSTALLER_SIM_ADVANCED=1 || fails=$((fails + 1))
  gui_case dual_delete INSTALLER_SIM_MODE=dual INSTALLER_SIM_DUAL=delete INSTALLER_SIM_ONLINE=1 || fails=$((fails + 1))
fi

if [[ "$MODE" == all || "$MODE" == gui-rest ]]; then
  gui_case fail INSTALLER_SIM_MODE=fresh INSTALLER_SIM_ONLINE=1 INSTALLER_STUB_EXIT=1 || fails=$((fails + 1))
  gui_case fresh_local INSTALLER_SIM_MODE=fresh INSTALLER_SIM_ONLINE=1 INSTALLER_SIM_LOCAL=1 INSTALLER_SIM_SOURCE=local || fails=$((fails + 1))
  gui_case offline INSTALLER_SIM_MODE=fresh INSTALLER_SIM_ONLINE=0 INSTALLER_SIM_LOCAL=0 || fails=$((fails + 1))
  gui_case wifi INSTALLER_SIM_WIFI=1 INSTALLER_SIM_ONLINE=0 INSTALLER_SIM_LOCAL=0 || fails=$((fails + 1))
  gui_case kde_nv INSTALLER_SIM_MODE=fresh INSTALLER_SIM_ONLINE=1 INSTALLER_SIM_LOCAL=0 INSTALLER_SIM_DESKTOP=kde INSTALLER_SIM_NVIDIA=1 || fails=$((fails + 1))
  gui_case confirm_back INSTALLER_SIM_ONLINE=1 INSTALLER_SIM_CONFIRM_BACK=1 || fails=$((fails + 1))
  gui_case no_shrink INSTALLER_SIM_MODE=dual INSTALLER_SIM_DUAL=no_shrink INSTALLER_SIM_ONLINE=1 || fails=$((fails + 1))
  gui_case ext_incomplete INSTALLER_SIM_DISK_GATE=external INSTALLER_SIM_FRZR=incomplete INSTALLER_SIM_ONLINE=1 || fails=$((fails + 1))
  gui_case deploy_fail INSTALLER_SIM_MODE=fresh INSTALLER_SIM_ONLINE=1 INSTALLER_STUB_DEPLOY_EXIT=1 || fails=$((fails + 1))
fi

echo "catalog-run fails=$fails" | tee -a "$ROOT/.sim/catalog-run.log"
exit "$fails"

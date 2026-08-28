#!/usr/bin/env bash
# Product-branch coverage: flow unit tests + TUI Pilot cases + GUI page map.
# Does not launch GTK. Does not use INSTALLER_SIM_AUTO. Not VT/keyboard proof.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%H%M%S)"
SHOT="${INSTALLER_COVERAGE_SHOTS:-$ROOT/.sim/coverage-$STAMP}"
mkdir -p "$SHOT"
export INSTALLER_COVERAGE_SHOTS="$SHOT"
export PYTHONPATH="$ROOT/skorionos/airootfs/usr/local/lib${PYTHONPATH:+:$PYTHONPATH}"
echo "coverage shots → $SHOT (not portal/VT acceptance)"
uv run --with pytest --with textual --with pillow pytest tests/installer -q --tb=short
echo "unique shots:"
ls -1 "$SHOT" | sed 's/^/  /' || true

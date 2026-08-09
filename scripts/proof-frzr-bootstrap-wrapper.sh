#!/usr/bin/env bash
# Drop-in for INSTALLER_FRZR_BOOTSTRAP: log parent chain, then exec real binary.
set -euo pipefail
LOG="${INSTALLER_PROOF_CHAIN_LOG:?INSTALLER_PROOF_CHAIN_LOG unset}"
REAL="${INSTALLER_PROOF_REAL_FRZR:-/usr/bin/frzr-bootstrap}"

{
  echo "===== WRAPPER EXEC at $(date -Iseconds) ====="
  echo "wrapper_pid=$$"
  echo "wrapper_ppid=$PPID"
  echo "wrapper_argv=$*"
  echo "parent_cmdline=$(tr '\0' ' ' </proc/$PPID/cmdline 2>/dev/null || true)"
  echo "parent_exe=$(readlink /proc/$PPID/exe 2>/dev/null || true)"
  cur=$PPID
  for d in 1 2 3 4 5 6; do
    echo "ancestor$d pid=$cur cmdline=$(tr '\0' ' ' </proc/$cur/cmdline 2>/dev/null || true)"
    echo "ancestor$d exe=$(readlink /proc/$cur/exe 2>/dev/null || true)"
    cur=$(awk '/^PPid:/{print $2}' /proc/$cur/status 2>/dev/null || echo 0)
    [[ "$cur" == "0" || -z "$cur" ]] && break
  done
  if command -v pstree >/dev/null; then
    echo "----- pstree from parent -----"
    pstree -ap "$PPID" 2>/dev/null || pstree -p "$PPID" 2>/dev/null || true
  fi
  echo "----- parent environ (installer-related) -----"
  tr '\0' '\n' </proc/$PPID/environ 2>/dev/null | grep -E 'INSTALLER_|PYTHONPATH|FRZR_' || true
  echo "===== exec $REAL $* ====="
} >>"$LOG"

exec "$REAL" "$@"

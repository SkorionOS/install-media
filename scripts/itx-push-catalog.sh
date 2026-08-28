#!/usr/bin/env bash
# From ITX: wait for Win5 SSH, rsync installer, install textual, run catalog shots, pull PNGs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_ROOT="${REMOTE_ROOT:-/tmp/install-media}"
SSH_BASE=(-o BatchMode=yes -o ConnectTimeout=8 -o HostKeyAlias=win5.local)

pick_host() {
  if ssh "${SSH_BASE[@]}" gamer@win5.local "echo ok" >/dev/null 2>&1; then
    echo "gamer@win5.local"
    return 0
  fi
  local ll
  for ll in \
    "gamer@fe80::6e4c:e2ff:fe0b:3141%wlp15s0" \
    "gamer@fe80::6e4c:e2ff:fe0b:3141%enp14s0"; do
    if ssh -6 "${SSH_BASE[@]}" "$ll" "echo ok" >/dev/null 2>&1; then
      echo "$ll"
      return 0
    fi
  done
  if ping -c 1 -W 1 192.168.50.135 >/dev/null 2>&1 \
    && ssh "${SSH_BASE[@]}" gamer@192.168.50.135 "echo ok" >/dev/null 2>&1; then
    echo "gamer@192.168.50.135"
    return 0
  fi
  return 1
}

wait_host() {
  local i
  for i in $(seq 1 180); do
    if HOST="$(pick_host)"; then
      echo "$HOST"
      return 0
    fi
    echo "Win5 unreachable, retry $i/180" >&2
    sleep 5
  done
  return 1
}

echo "waiting for Win5..."
HOST="$(wait_host)"
echo "Win5 host=$HOST"

ssh_win() {
  if [[ "$HOST" == *fe80* ]]; then
    ssh -6 "${SSH_BASE[@]}" "$HOST" "$@"
  else
    ssh "${SSH_BASE[@]}" "$HOST" "$@"
  fi
}

rsync_to() {
  local src="$1" dest="$2"
  if [[ "$HOST" == *fe80* ]]; then
    rsync -az -e "ssh -6 ${SSH_BASE[*]}" "$src" "$dest"
  else
    rsync -az -e "ssh ${SSH_BASE[*]}" "$src" "$dest"
  fi
}

rsync_from() {
  local src="$1" dest="$2"
  if [[ "$HOST" == *fe80* ]]; then
    rsync -az -e "ssh -6 ${SSH_BASE[*]}" "$src" "$dest"
  else
    rsync -az -e "ssh ${SSH_BASE[*]}" "$src" "$dest"
  fi
}

ssh_win "mkdir -p $REMOTE_ROOT/scripts $REMOTE_ROOT/skorionos/airootfs/usr/local/lib/installer $REMOTE_ROOT/.sim"
rsync_to "$ROOT/scripts/" "$HOST:$REMOTE_ROOT/scripts/"
rsync_to "$ROOT/skorionos/airootfs/usr/local/lib/installer/" \
  "$HOST:$REMOTE_ROOT/skorionos/airootfs/usr/local/lib/installer/"

BUNDLE=/tmp/textual-bundle
rm -rf "$BUNDLE"
mkdir -p "$BUNDLE"
SP=/tmp/win5-installer-venv/lib/python3.14/site-packages
if [[ -d "$SP/textual" ]]; then
  for d in textual textual-8.2.8.dist-info rich rich-15.0.0.dist-info \
    markdown_it markdown_it_py-4.2.0.dist-info mdit_py_plugins mdit_py_plugins-0.6.1.dist-info \
    pygments pygments-2.21.0.dist-info platformdirs platformdirs-4.11.4.dist-info \
    linkify_it linkify_it_py-2.1.1.dist-info uc_micro uc_micro_py-2.0.0.dist-info; do
    [[ -e "$SP/$d" ]] && cp -a "$SP/$d" "$BUNDLE/"
  done
  ssh_win "mkdir -p /tmp/textual-bundle"
  rsync_to "$BUNDLE/" "$HOST:/tmp/textual-bundle/"
fi

ssh_win bash -s <<'REMOTE'
set -euo pipefail
ROOT=/tmp/install-media
python3 -m venv --system-site-packages /tmp/win5-installer-venv
PY=/tmp/win5-installer-venv/bin/python
ver="$($PY -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ -d /tmp/textual-bundle/textual ]]; then
  mkdir -p "/tmp/win5-installer-venv/lib/$ver/site-packages"
  cp -a /tmp/textual-bundle/. "/tmp/win5-installer-venv/lib/$ver/site-packages/"
fi
$PY -c "import textual, PIL, numpy; print('ok', textual.__version__)"
sudo -n systemctl unmask --runtime sddm.service 2>/dev/null || true
if ! pgrep -x gnome-shell >/dev/null; then
  echo "gnome-shell down — rewriting wayland sentinel + restart sddm"
  mkdir -p "$HOME/.config"
  echo wayland > "$HOME/.config/steamos-session-select"
  sudo -n systemctl restart sddm.service || true
  sleep 8
fi
export INSTALLER_PYTHON=$PY
export INSTALLER_VT_TTY=3
cd "$ROOT"
bash scripts/win5-catalog-shots.sh
REMOTE

mkdir -p "$ROOT/.sim"
rsync_from "$HOST:$REMOTE_ROOT/.sim/" "$ROOT/.sim/"
echo "pulled shots; catalog-run:"
cat "$ROOT/.sim/catalog-run.log" 2>/dev/null || true

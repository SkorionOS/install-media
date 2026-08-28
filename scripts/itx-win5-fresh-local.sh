#!/usr/bin/env bash
# Wait for Win5 TCP/22, rsync, run TUI fresh_local VT shots, pull PNGs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE=/tmp/install-media
SSH_BASE=(-o BatchMode=yes -o ConnectTimeout=5 -o HostKeyAlias=win5.local)
HOST=""

wol() {
  python3 -c '
import socket
mac=bytes.fromhex("6c4ce20b3141")
pkt=b"\xff"*6+mac*16
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
for dst in ("192.168.50.255","255.255.255.255"):
    try: s.sendto(pkt,(dst,9))
    except Exception: pass
print("wol")
'
}

tcp_ok() {
  python3 -c '
import socket,sys
s=socket.socket(); s.settimeout(1.2)
try:
    s.connect((sys.argv[1],22)); sys.exit(0)
except Exception:
    sys.exit(1)
finally:
    s.close()
' "$1"
}

find_win5_ip() {
  python3 - <<'PY'
import socket, subprocess, concurrent.futures
want = "AAAAC3NzaC1lZDI1NTE5AAAAIEonYoSeINfON4/WkKqKQ5yzRFLC3xEyG7LRUVuNHZe8"

def probe(ip):
    s = socket.socket(); s.settimeout(0.25)
    try:
        s.connect((ip, 22)); s.close()
    except Exception:
        return None
    r = subprocess.run(["ssh-keyscan", "-T", "2", "-t", "ed25519", ip], capture_output=True, text=True)
    if want in r.stdout:
        return ip
    return None

ips = [f"192.168.50.{i}" for i in range(1, 255)]
with concurrent.futures.ThreadPoolExecutor(48) as ex:
    for ip in ex.map(probe, ips):
        if ip:
            print(ip)
            break
PY
}

pick() {
  local ip
  ip="$(find_win5_ip || true)"
  if [[ -n "${ip:-}" ]]; then
    if ssh "${SSH_BASE[@]}" "gamer@$ip" "echo ok" >/dev/null 2>&1; then
      echo "gamer@$ip"
      return 0
    fi
  fi
  ip=$(timeout 2 avahi-resolve -n win5.local 2>/dev/null | awk '{print $2; exit}' || true)
  if [[ -n "${ip:-}" ]] && tcp_ok "$ip"; then
    if ssh "${SSH_BASE[@]}" "gamer@$ip" "echo ok" >/dev/null 2>&1; then
      echo "gamer@$ip"
      return 0
    fi
  fi
  return 1
}

echo "waiting for Win5 SSH (fresh_offline)"
wol
for i in $(seq 1 400); do
  if HOST="$(pick)"; then
    echo "SSHOK $HOST"
    break
  fi
  echo "retry $i/400"
  if (( i % 5 == 0 )); then wol; fi
  sleep 3
done
[[ -n "$HOST" ]] || { echo "FAIL no Win5 SSH"; exit 2; }

ssh_win() {
  if [[ "$HOST" == *fe80* ]]; then
    ssh -6 "${SSH_BASE[@]}" "$HOST" "$@"
  else
    ssh "${SSH_BASE[@]}" "$HOST" "$@"
  fi
}
rsync_e() {
  if [[ "$HOST" == *fe80* ]]; then
    echo "ssh -6 ${SSH_BASE[*]}"
  else
    echo "ssh ${SSH_BASE[*]}"
  fi
}

ssh_win "mkdir -p $REMOTE/scripts $REMOTE/skorionos/airootfs/usr/local/lib/installer $REMOTE/.sim"
rsync -az -e "$(rsync_e)" "$ROOT/scripts/" "$HOST:$REMOTE/scripts/"
rsync -az -e "$(rsync_e)" \
  "$ROOT/skorionos/airootfs/usr/local/lib/installer/" \
  "$HOST:$REMOTE/skorionos/airootfs/usr/local/lib/installer/"

BUNDLE=/tmp/textual-bundle
if [[ ! -d $BUNDLE/textual ]]; then
  mkdir -p "$BUNDLE"
  SP=/tmp/win5-installer-venv/lib/python3.14/site-packages
  for d in textual textual-8.2.8.dist-info rich rich-15.0.0.dist-info \
    markdown_it markdown_it_py-4.2.0.dist-info mdit_py_plugins mdit_py_plugins-0.6.1.dist-info \
    pygments pygments-2.21.0.dist-info platformdirs platformdirs-4.11.4.dist-info \
    linkify_it linkify_it_py-2.1.1.dist-info uc_micro uc_micro_py-2.0.0.dist-info; do
    [[ -e "$SP/$d" ]] && cp -a "$SP/$d" "$BUNDLE/"
  done
fi
ssh_win "mkdir -p /tmp/textual-bundle"
rsync -az -e "$(rsync_e)" "$BUNDLE/" "$HOST:/tmp/textual-bundle/"

ssh_win bash -s <<'REMOTE'
set -euo pipefail
ROOT=/tmp/install-media
python3 -m venv --system-site-packages /tmp/win5-installer-venv
PY=/tmp/win5-installer-venv/bin/python
ver="$($PY -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')"
mkdir -p "/tmp/win5-installer-venv/lib/$ver/site-packages"
cp -a /tmp/textual-bundle/. "/tmp/win5-installer-venv/lib/$ver/site-packages/"
$PY -c "import textual,PIL,numpy; print('pyok', textual.__version__)"
export INSTALLER_PYTHON=$PY
export INSTALLER_VT_TTY=3
export INSTALLER_SIM_MODE=fresh
export INSTALLER_SIM_ONLINE=0
export INSTALLER_SIM_LOCAL=0
unset INSTALLER_SIM_SOURCE INSTALLER_SIM_WIFI || true
export INSTALLER_VT_OUT="$ROOT/.sim/vt-offline-$(date +%H%M%S)"
cd "$ROOT"
echo "VT_OUT=$INSTALLER_VT_OUT"
"$PY" "$ROOT/scripts/agent-vt-fb-shots.py"
REMOTE

mkdir -p "$ROOT/.sim"
rsync -az -e "$(rsync_e)" "$HOST:$REMOTE/.sim/" "$ROOT/.sim/"
echo "PULL_DONE"
ls -1dt "$ROOT"/.sim/vt-offline-* 2>/dev/null | head -3
cat "$(ls -1dt "$ROOT"/.sim/vt-offline-*/RESULT.txt 2>/dev/null | head -1)" || true

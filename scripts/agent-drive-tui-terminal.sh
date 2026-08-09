#!/usr/bin/env bash
# Agent drives the TUI in a real gnome-terminal and captures window screenshots.
# Principle: agent operates; user does not click.
set -euo pipefail

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export DISPLAY="${DISPLAY:-:0}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/1000/bus}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${INSTALLER_SIM_DIR:-$ROOT/.sim}/compare"
mkdir -p "$OUT"
LAUNCH="$ROOT/scripts/dev-run-tui-terminal.sh"

pkill -f 'installer.tui_main' 2>/dev/null || true
pkill -f 'SkorionOS-TUI-LIVE' 2>/dev/null || true
sleep 0.4

# Launch terminal
systemd-run --user \
  --setenv=DISPLAY="$DISPLAY" \
  --setenv=WAYLAND_DISPLAY="$WAYLAND_DISPLAY" \
  --setenv=XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
  --setenv=DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" \
  gnome-terminal --geometry=100x32 --title="SkorionOS-TUI-LIVE" -- "$LAUNCH"

# Wait for TUI process
for i in $(seq 1 40); do
  if pgrep -f 'python3 -m installer.tui_main' >/dev/null; then
    break
  fi
  sleep 0.25
done
sleep 1.2

if ! pgrep -f 'python3 -m installer.tui_main' >/dev/null; then
  echo "FAIL: TUI did not start" >&2
  exit 1
fi

# Key driver: xdotool (XWayland) preferred
if ! command -v xdotool >/dev/null; then
  echo "FAIL: xdotool missing; cannot send keys without user" >&2
  # fallback: kill and use tmux agent-driven path
  exec "$ROOT/scripts/agent-drive-tui-tmux.sh"
fi

WID=""
for i in $(seq 1 30); do
  WID="$(xdotool search --name 'SkorionOS-TUI-LIVE' 2>/dev/null | tail -1 || true)"
  if [[ -n "$WID" ]]; then
    break
  fi
  sleep 0.2
done
echo "WID=$WID"
if [[ -z "$WID" ]]; then
  echo "FAIL: window not found" >&2
  exit 1
fi

xdotool windowactivate --sync "$WID" || true
xdotool windowfocus --sync "$WID" || true
sleep 0.4

shot() {
  local name="$1"
  sleep 0.4
  # Try window geometry crop via import
  if command -v import >/dev/null; then
    # import active window
    import -window "$WID" "$OUT/$name.png" 2>/dev/null \
      || import -window root "$OUT/$name.png" 2>/dev/null \
      || true
  fi
  if [[ ! -s "$OUT/$name.png" ]] && command -v gnome-screenshot >/dev/null; then
    gnome-screenshot -w -f "$OUT/$name.png" 2>/dev/null || true
  fi
  if [[ -s "$OUT/$name.png" ]]; then
    echo "SHOT $name $(file -b "$OUT/$name.png")"
  else
    echo "SHOT_FAIL $name" >&2
  fi
}

shot live_01_disk
for step in live_02_mode live_03_source live_04_channel live_05_desktop live_06_nvidia; do
  xdotool key --window "$WID" Return
  sleep 0.6
  shot "$step"
done
shot live_07_confirm
xdotool key --window "$WID" Right
sleep 0.35
shot live_08_confirm_go
xdotool key --window "$WID" Return
sleep 1.0
shot live_09_progress
# wait for stubs to finish
for i in $(seq 1 40); do
  sleep 0.25
  if ! pgrep -f 'python3 -m installer.tui_main' >/dev/null; then
    break
  fi
done
shot live_10_final

# Also capture classic dialog in another terminal for side-by-side
CLASSIC_SCRIPT="$OUT/run_classic_dialog.sh"
cat >"$CLASSIC_SCRIPT" <<'EOF'
#!/bin/bash
export TERM=xterm-256color
export DIALOGRC=/tmp/dialogrc-ui-compare
cat > "$DIALOGRC" <<'RC'
use_colors = ON
use_shadow = ON
screen_color = (CYAN,BLUE,ON)
shadow_color = (BLACK,BLACK,ON)
dialog_color = (BLACK,WHITE,OFF)
title_color = (BLUE,WHITE,ON)
border_color = (WHITE,WHITE,ON)
button_active_color = (WHITE,BLUE,ON)
button_inactive_color = (BLACK,WHITE,OFF)
button_label_active_color = (WHITE,BLUE,ON)
button_label_inactive_color = (BLACK,WHITE,ON)
menubox_color = (BLACK,WHITE,OFF)
menubox_border_color = (WHITE,WHITE,ON)
item_color = (BLACK,WHITE,OFF)
item_selected_color = (WHITE,BLUE,ON)
tag_color = (BLUE,WHITE,ON)
tag_selected_color = (YELLOW,BLUE,ON)
RC
dialog --colors --title "\Z3警告\Zn" --defaultno \
  --yes-label "继续" --no-label "取消安装" --extra-button --extra-label "帮助" \
  --yesno "警告: SkorionOS 将被安装到以下磁盘:\n\n    nvme0n1 - 512G Samsung SSD\n\n您是否要继续?\n(在后续步骤可进行更详细的安装选项设置)\n\n安装程序版本: v2.1.5" 12 70
sleep 60
EOF
chmod +x "$CLASSIC_SCRIPT"

systemd-run --user \
  --setenv=DISPLAY="$DISPLAY" \
  --setenv=WAYLAND_DISPLAY="$WAYLAND_DISPLAY" \
  --setenv=XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
  --setenv=DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" \
  gnome-terminal --geometry=100x32 --title="SkorionOS-CLASSIC-DIALOG" -- "$CLASSIC_SCRIPT"
sleep 2.0
CWID="$(xdotool search --name 'SkorionOS-CLASSIC-DIALOG' 2>/dev/null | tail -1 || true)"
echo "CWID=$CWID"
if [[ -n "$CWID" ]]; then
  xdotool windowactivate --sync "$CWID" || true
  sleep 0.5
  import -window "$CWID" "$OUT/classic_01_confirm.png" 2>/dev/null || true
  echo "SHOT classic_01_confirm $(file -b "$OUT/classic_01_confirm.png" 2>/dev/null || true)"
  # close dialog
  xdotool key --window "$CWID" Escape || true
fi

ls -la "$OUT"/live_*.png "$OUT"/classic_*.png 2>&1 | tee "$OUT/SHOTS.txt"
echo "DONE OUT=$OUT"

#!/usr/bin/env bash
# Fallback: agent drives TUI in tmux (still agent-operated, not user).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${INSTALLER_SIM_DIR:-$ROOT/.sim}/compare"
mkdir -p "$OUT"
SESSION=agent-tui-drive

tmux kill-session -t "$SESSION" 2>/dev/null || true
pkill -f 'installer.tui_main' 2>/dev/null || true

export PYTHONPATH="$ROOT/skorionos/airootfs/usr/local/lib"
export TERM=xterm-256color
export COLORTERM=truecolor
export INSTALLER_DEV=1
export INSTALLER_SIMULATION=1
export INSTALLER_SIM_DISK=nvme0n1
export INSTALLER_FRZR_BOOTSTRAP="$ROOT/scripts/installer-stubs/frzr-bootstrap"
export INSTALLER_FRZR_DEPLOY="$ROOT/scripts/installer-stubs/frzr-deploy"
export INSTALLER_STUB_SLEEP=0
export INSTALLER_LOG_FILE="$OUT/tui-live.log"
unset INSTALLER_SIM_AUTO || true
unset INSTALLER_DRY_RUN || true

tmux new-session -d -s "$SESSION" -x 100 -y 32 \
  "cd '$ROOT' && python3 -m installer.tui_main; tmux wait-for -S tui-done"

sleep 1.2

cap() {
  local name="$1"
  sleep 0.35
  tmux capture-pane -t "$SESSION" -p -e >"$OUT/${name}.ansi" 2>/dev/null || true
  tmux capture-pane -t "$SESSION" -p >"$OUT/${name}.txt" 2>/dev/null || true
  # Render ANSI to PNG with script that uses PIL if available — ONLY as secondary;
  # primary evidence is .ansi/.txt from live tmux. Prefer real window shots when xdotool path works.
  echo "CAP $name"
  head -20 "$OUT/${name}.txt" || true
}

cap live_01_disk
for step in live_02_mode live_03_source live_04_channel live_05_desktop live_06_nvidia; do
  tmux send-keys -t "$SESSION" Enter
  sleep 0.55
  cap "$step"
done
cap live_07_confirm
tmux send-keys -t "$SESSION" Right
sleep 0.3
cap live_08_confirm_go
tmux send-keys -t "$SESSION" Enter
sleep 1.0
cap live_09_progress
sleep 2.0
cap live_10_final

# Classic dialog in tmux for comparison
tmux kill-session -t agent-classic 2>/dev/null || true
tmux new-session -d -s agent-classic -x 100 -y 32 bash -lc '
export TERM=linux
export DIALOGRC=/tmp/dialogrc-ui-compare
cat > "$DIALOGRC" <<RC
use_colors = ON
use_shadow = ON
screen_color = (CYAN,BLUE,ON)
dialog_color = (BLACK,WHITE,OFF)
title_color = (BLUE,WHITE,ON)
border_color = (WHITE,WHITE,ON)
button_active_color = (WHITE,BLUE,ON)
button_inactive_color = (BLACK,WHITE,OFF)
button_label_active_color = (WHITE,BLUE,ON)
button_label_inactive_color = (BLACK,WHITE,ON)
RC
dialog --colors --title "\Z3警告\Zn" --defaultno \
  --yes-label "继续" --no-label "取消安装" --extra-button --extra-label "帮助" \
  --yesno "警告: SkorionOS 将被安装到以下磁盘:\n\n    nvme0n1 - 512G Samsung SSD\n\n您是否要继续?\n(在后续步骤可进行更详细的安装选项设置)\n\n安装程序版本: v2.1.5" 12 70
sleep 5
'
sleep 1.2
tmux capture-pane -t agent-classic -p >"$OUT/classic_01_confirm.txt"
tmux send-keys -t agent-classic Escape
tmux kill-session -t agent-classic 2>/dev/null || true
tmux kill-session -t "$SESSION" 2>/dev/null || true
pkill -f 'installer.tui_main' 2>/dev/null || true

{
  echo "AGENT-DRIVEN capture (tmux). Agent sent keys; user did not operate."
  echo
  echo "=== CLASSIC dialog confirm ==="
  cat "$OUT/classic_01_confirm.txt"
  echo
  echo "=== NEW TUI disk ==="
  cat "$OUT/live_01_disk.txt"
  echo
  echo "=== NEW TUI confirm ==="
  cat "$OUT/live_07_confirm.txt"
} | tee "$OUT/COMPARE.txt"

echo "DONE $OUT"

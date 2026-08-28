"""Textual installer — GTK page order + real widgets + verified screenshots.

Screenshots are Textual export_screenshot AFTER layout, rejected if the SVG is
an empty/title-only frame. Not txt→PNG theater.
"""

from __future__ import annotations

import glob
import os
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.theme import Theme
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    OptionList,
    ProgressBar,
    RadioButton,
    RadioSet,
    Rule,
    Static,
)
from textual.content import Content
from textual.style import Style
from textual.widgets.option_list import Option

# dialog(1) 16-color theme — matches dialog --create-rc defaults on VT.
# ansi=True → native SGR 30–47; truecolor is crushed on fbcon.
SKORION_CONSOLE = Theme(
    name="skorion-console",
    primary="ansi_blue",
    secondary="ansi_bright_white",
    accent="ansi_bright_yellow",
    foreground="ansi_bright_white",
    background="ansi_blue",
    surface="ansi_bright_white",
    panel="ansi_bright_white",
    boost="ansi_bright_blue",
    success="ansi_green",
    warning="ansi_bright_yellow",
    error="ansi_red",
    dark=True,
    ansi=True,
    variables={
        "block-cursor-background": "ansi_blue",
        "block-cursor-foreground": "ansi_bright_white",
        "block-cursor-blurred-background": "ansi_blue",
        "block-cursor-blurred-foreground": "ansi_bright_yellow",
        "border": "ansi_bright_white",
        "border-blurred": "ansi_bright_white",
        "footer-key-foreground": "ansi_bright_yellow",
        "input-selection-background": "ansi_blue",
        "input-selection-foreground": "ansi_bright_white",
        "button-foreground": "ansi_black",
        "button-color-foreground": "ansi_bright_white",
    },
)

from installer.engine import (
    BootstrapService,
    DeployService,
    EventKind,
    InstallPlan,
    ProgressEvent,
)
from installer.flow import (
    after_bootstrap_success,
    after_deploy_success,
    after_disk_selected,
    after_dual_selected,
    after_frzr_check,
    apply_advanced_options,
    default_advanced,
    log_file as installer_log_file,
    poweroff as flow_poweroff,
    reboot as flow_reboot,
    shrinkable_partitions,
)
from installer.config import config as installer_config
from installer.flow import copy as flow_copy
from installer.tui.chrome import DIALOG_CSS, compose_dialog
from installer.tui.wifi import WifiNetwork, WifiService

VERSION = installer_config.version
MODE_CN = {"fresh": "全新安装", "repair": "修复安装", "dual": "双系统"}
SOURCE_CN = {"online": "在线安装", "local": "本地安装"}


# ---------------------------------------------------------------------------
# System status bar — mirrors GUI StatusBar (battery / net / time)
# ---------------------------------------------------------------------------


def _format_speed(bytes_per_sec: int) -> str:
    if bytes_per_sec < 0:
        bytes_per_sec = 0
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec} B/s"
    if bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    if bytes_per_sec < 1024 * 1024 * 1024:
        return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
    return f"{bytes_per_sec / (1024 * 1024 * 1024):.2f} GB/s"


def _battery_text() -> str:
    try:
        paths = glob.glob("/sys/class/power_supply/BAT*")
        if not paths:
            return "AC 电源"
        bat = paths[0]
        with open(f"{bat}/capacity", encoding="utf-8") as fh:
            capacity = int(fh.read().strip())
        with open(f"{bat}/status", encoding="utf-8") as fh:
            status = fh.read().strip()
        if status == "Charging":
            return f"电量 {capacity}% 充电中"
        if status == "Full":
            return f"电量 {capacity}% 已充满"
        return f"电量 {capacity}%"
    except Exception:
        return "电量 --"


class SystemStatusBar(Static):
    """Top bar matching GUI StatusBar: battery · ↓/↑ · time (single Static — must paint)."""

    DEFAULT_CSS = """
    SystemStatusBar {
        dock: top;
        width: 100%;
        height: 1;
        min-height: 1;
        background: ansi_blue;
        color: ansi_bright_cyan;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__(" … ", id="statusbar")
        self._last_rx = 0
        self._last_tx = 0
        self._iface: Optional[str] = None

    def on_mount(self) -> None:
        self._tick()
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        down, up = self._net_speeds()
        left = f"{_battery_text()}   ↓ {down}  ↑ {up}"
        right = datetime.now().strftime("%Y-%m-%d %H:%M")
        width = max(int(self.size.width or 0), 80)
        # keep one row: left … right
        gap = max(1, width - len(left) - len(right) - 2)
        self.update(f"{left}{' ' * gap}{right}")

    def _net_speeds(self) -> Tuple[str, str]:
        try:
            ifaces = [
                p.split("/")[-1]
                for p in glob.glob("/sys/class/net/*")
                if "lo" not in p
            ]
            active = None
            for iface in ifaces:
                try:
                    with open(
                        f"/sys/class/net/{iface}/carrier", encoding="utf-8"
                    ) as fh:
                        if fh.read().strip() == "1":
                            active = iface
                            break
                except Exception:
                    continue
            if not active:
                self._last_rx = 0
                self._last_tx = 0
                self._iface = None
                return "--", "--"
            with open(
                f"/sys/class/net/{active}/statistics/rx_bytes", encoding="utf-8"
            ) as fh:
                rx = int(fh.read().strip())
            with open(
                f"/sys/class/net/{active}/statistics/tx_bytes", encoding="utf-8"
            ) as fh:
                tx = int(fh.read().strip())
            if self._last_rx > 0 and self._iface == active:
                down = _format_speed(max(0, rx - self._last_rx))
                up = _format_speed(max(0, tx - self._last_tx))
            else:
                down, up = "0 B/s", "0 B/s"
            self._last_rx = rx
            self._last_tx = tx
            self._iface = active
            return down, up
        except Exception:
            return "--", "--"


def list_local_frzr_files() -> List[dict]:
    """Local install candidates — GUI local_frzr_files shape."""
    from installer.flow.lifecycle import sim_local_frzr_files

    return sim_local_frzr_files()


def list_disks() -> List[Tuple[str, str]]:
    from installer.flow.env import simulation

    prefer = os.environ.get("INSTALLER_SIM_DISK", "").removeprefix("/dev/")
    if not simulation():
        from installer.backend.disk_utils import list_available_disks

        disks = [(d["name"], d["description"]) for d in list_available_disks()]
        if prefer:
            disks = [d for d in disks if d[0] == prefer] or disks
        return disks

    allow_loop = True
    try:
        result = subprocess.run(
            ["lsblk", "-dn", "-o", "NAME,SIZE,MODEL,TYPE"],
            capture_output=True,
            text=True,
            check=False,
        )
        disks: List[Tuple[str, str]] = []
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) < 2:
                continue
            dtype = fields[-1]
            if dtype == "disk":
                pass
            elif allow_loop and dtype == "loop":
                pass
            else:
                continue
            name = fields[0]
            size = fields[1]
            model = " ".join(fields[2:-1]) if len(fields) > 3 else ""
            if dtype == "loop":
                model = (model + " [SIM]").strip()
            disks.append((name, f"{size}  {model}".strip()))
        if prefer:
            disks = [d for d in disks if d[0] == prefer] or disks
            disks.sort(key=lambda item: 0 if item[0] == prefer else 1)
        if disks:
            return disks
    except Exception:
        pass
    return [("nvme0n1", "953.9G (mock)"), ("sda", "500G (mock)")]


class ProductCheckbox(Checkbox):
    """Off shows an empty box; on shows X. Textual's default always paints X."""

    @property
    def _button(self) -> Content:
        button_style = self.get_visual_style("toggle--button")
        side_style = Style(
            foreground=button_style.background,
            background=self.background_colors[1],
        )
        inner = "X" if self.value else " "
        return Content.assemble(
            (self.BUTTON_LEFT, side_style),
            (inner, button_style),
            (self.BUTTON_RIGHT, side_style),
        )


def _sim_auto() -> bool:
    return os.environ.get("INSTALLER_SIM_AUTO", "") in ("1", "true", "yes")


def _shot_dir() -> Optional[Path]:
    raw = os.environ.get("INSTALLER_SHOT_DIR", "").strip()
    return Path(raw) if raw else None


def _window_shot_mode() -> bool:
    """True = external terminal window + portal screenshots (no SVG export)."""
    return os.environ.get("INSTALLER_WINDOW_SHOT", "") in ("1", "true", "yes")


def _announce_page(label: str) -> None:
    """Signal page-ready for external window capture scripts.

    Uses an append-only queue so fast page transitions cannot overwrite a
    label before the watcher captures it.
    """
    marker = os.environ.get("INSTALLER_PAGE_MARKER", "").strip()
    if not marker:
        return
    try:
        path = Path(marker)
        # Keep last label for compatibility + append to .queue
        path.write_text(label + "\n", encoding="utf-8")
        q = path.with_suffix(path.suffix + ".queue")
        with q.open("a", encoding="utf-8") as fh:
            fh.write(label + "\n")
    except Exception:
        pass


def _trace_focus(widget: object) -> None:
    """Append focused widget id for real keyboard-flow verification."""
    path = os.environ.get("INSTALLER_FOCUS_FILE", "").strip()
    if not path:
        return
    try:
        wid = getattr(widget, "id", None) or type(widget).__name__
        with Path(path).open("a", encoding="utf-8") as fh:
            fh.write(f"{time.time():.3f}\t{wid}\n")
    except Exception:
        pass


def _wait_page_ack(label: str) -> None:
    """Block until watcher ACKs this page (real window screenshot taken)."""
    if not _window_shot_mode():
        return
    ack = os.environ.get("INSTALLER_PAGE_ACK", "").strip()
    if not ack:
        return
    deadline = time.time() + float(os.environ.get("INSTALLER_PAGE_ACK_TIMEOUT", "12"))
    while time.time() < deadline:
        try:
            if Path(ack).is_file() and Path(ack).read_text(encoding="utf-8").strip() == label:
                return
        except Exception:
            pass
        time.sleep(0.05)


_SHOT_SEQ = 0
_SHOT_LOCK = threading.Lock()
_SHOT_TAKEN: set[str] = set()


def _svg_is_real_frame(svg: str) -> bool:
    """Reject title-bar-only / empty exports (the 'fake' 8KB strips)."""
    if len(svg) < 12000:
        return False
    # Must have substantial terminal rows of content, not just chrome.
    # Rich SVG uses many <text> nodes; require enough non-trivial ones.
    texts = re.findall(r"<text[^>]*>([^<]+)</text>", svg)
    joined = " ".join(t.replace("&#160;", " ") for t in texts)
    # Strip common title-only noise
    body = joined
    for noise in ("SkorionOS", "安装程序", "v2.1.5", "Fira"):
        body = body.replace(noise, "")
    # Need real page copy
    meaningful = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", body)
    if len(meaningful) < 6:
        return False
    # viewBox height should not be a thin strip
    m = re.search(r'viewBox="0 0 [0-9.]+ ([0-9.]+)"', svg)
    if m and float(m.group(1)) < 200:
        return False
    return True


def _take_screen_shot(app: App, label: str, *, allow_dup: bool = False) -> bool:
    global _SHOT_SEQ
    dest = _shot_dir()
    if dest is None:
        return False
    with _SHOT_LOCK:
        if not allow_dup and label in _SHOT_TAKEN:
            return True
        try:
            svg = app.export_screenshot()
            if not _svg_is_real_frame(svg):
                return False
            dest.mkdir(parents=True, exist_ok=True)
            _SHOT_SEQ += 1
            svg_path = dest / f"{_SHOT_SEQ:02d}_{label}.svg"
            png_path = dest / f"{_SHOT_SEQ:02d}_{label}.png"
            svg_path.write_text(svg, encoding="utf-8")
            subprocess.run(
                ["magick", str(svg_path), str(png_path)],
                check=False,
                capture_output=True,
            )
            # Reject tiny PNGs (title-bar only ~8KB)
            if png_path.exists() and png_path.stat().st_size < 15000:
                svg_path.unlink(missing_ok=True)
                png_path.unlink(missing_ok=True)
                _SHOT_SEQ -= 1
                return False
            _SHOT_TAKEN.add(label)
            return True
        except Exception as exc:  # noqa: BLE001
            try:
                (dest / "shot_errors.txt").open("a", encoding="utf-8").write(
                    f"{label}: {exc}\n"
                )
            except Exception:
                pass
            return False


def _capture_when_ready(screen: Screen, label: str, tries: int = 12) -> None:
    """After layout: announce page for window shots; optionally SVG-export."""

    def after_layout() -> None:
        _announce_page(label)
        if _window_shot_mode():
            return  # real shots come from portal + gnome-terminal
        if _shot_dir() is None:
            return

        def attempt(n: int) -> None:
            if _take_screen_shot(screen.app, label):
                return
            if n + 1 >= tries:
                try:
                    dest = _shot_dir()
                    if dest:
                        (dest / "shot_errors.txt").open("a", encoding="utf-8").write(
                            f"{label}: gave up after {tries} empty frames\n"
                        )
                except Exception:
                    pass
                return
            screen.set_timer(0.08, lambda: attempt(n + 1))

        screen.set_timer(0.05, lambda: attempt(0))

    screen.call_after_refresh(after_layout)


# ---------------------------------------------------------------------------
# Chrome with REAL widgets (Button / RadioSet) — not painted Static lists
# ---------------------------------------------------------------------------


class PageFrame(Vertical):
    """Blue screen shell; dialog chrome CSS lives in installer.tui.chrome."""

    DEFAULT_CSS = (
        """
    PageFrame {
        width: 100%;
        height: 100%;
        background: ansi_blue;
        padding: 0;
        color: ansi_bright_white;
    }
    """
        + DIALOG_CSS
        + """
    /* RadioSet: Textual default uses border:tall which paints black slabs
       above/below the set on VT — kill ALL border edges. */
    RadioSet {
        width: 100%;
        height: auto;
        background: ansi_bright_white !important;
        border: none !important;
        border-top: none !important;
        border-bottom: none !important;
        padding: 0;
        color: ansi_black;
        background-tint: 0%;
    }
    RadioSet:focus,
    RadioSet:focus-within,
    RadioSet:blur {
        border: none !important;
        border-top: none !important;
        border-bottom: none !important;
        background-tint: 0% !important;
        background: ansi_bright_white !important;
    }
    RadioSet > RadioButton {
        width: 100%;
        height: 1;
        min-height: 1;
        max-height: 1;
        background: ansi_bright_white !important;
        border: none !important;
        border-top: none !important;
        border-bottom: none !important;
        color: ansi_black !important;
        padding: 0 1;
    }
    RadioSet > RadioButton:hover {
        background: ansi_blue !important;
        color: ansi_bright_white !important;
    }
    RadioSet > RadioButton.-selected,
    RadioSet > RadioButton.-on {
        width: 100%;
        background: ansi_blue !important;
        color: ansi_bright_white !important;
        text-style: bold;
    }
    RadioSet:focus > RadioButton.-selected,
    RadioSet:focus-within > RadioButton.-selected {
        background: ansi_blue !important;
        color: ansi_bright_yellow !important;
        text-style: bold;
    }
    /* Toggle glyph — no $panel black chips under labels. */
    RadioSet > RadioButton > .toggle--button {
        background: transparent !important;
        color: ansi_black !important;
        text-style: none;
    }
    RadioSet > RadioButton.-selected > .toggle--button,
    RadioSet > RadioButton.-on > .toggle--button {
        background: transparent !important;
        color: ansi_bright_yellow !important;
        text-style: bold;
    }
    Checkbox > .toggle--button {
        background: transparent !important;
        color: ansi_black !important;
        text-style: none;
    }
    Checkbox.-on > .toggle--button {
        background: transparent !important;
        color: ansi_bright_yellow !important;
        text-style: bold;
    }
    RadioSet > RadioButton.-selected > .toggle--label,
    RadioSet > RadioButton.-on > .toggle--label,
    RadioSet:focus > RadioButton.-selected > .toggle--label {
        background: transparent !important;
        color: ansi_bright_white !important;
    }
    RadioSet:focus > RadioButton.-selected > .toggle--label {
        color: ansi_bright_yellow !important;
    }
    #wifi_list {
        height: 1fr;
        min-height: 8;
        border: solid ansi_black;
        background: ansi_bright_white;
        color: ansi_black;
        padding: 0 1;
    }
    #wifi_list:focus {
        border: solid ansi_blue;
        background: ansi_bright_white;
    }
    #wifi_list > .option-list--option {
        color: ansi_black;
        padding: 0 1;
    }
    #wifi_list > .option-list--option-highlighted {
        background: ansi_blue;
        color: ansi_bright_white;
        text-style: bold;
    }
    #wifi_list:focus > .option-list--option-highlighted {
        background: ansi_blue;
        color: ansi_bright_yellow;
        text-style: bold;
    }
    #wifi_status {
        height: auto;
        margin-bottom: 1;
        width: 100%;
        color: ansi_black;
    }
    #wifi_hint {
        color: ansi_black;
        height: 1;
        width: 100%;
    }
    Input {
        width: 100%;
        margin: 1 0;
        background: ansi_bright_white;
        color: ansi_black;
        border: solid ansi_black;
        padding: 0 1;
    }
    Input:focus {
        border: solid ansi_blue;
        background: ansi_bright_white;
        color: ansi_black;
    }
    .section-label {
        color: ansi_black;
        text-style: bold underline;
        margin: 1 0 0 0;
        width: 100%;
        text-align: left;
    }
    #version_cols {
        width: 100%;
        height: auto;
        margin-top: 1;
    }
    #version_cols .ver_col {
        width: 1fr;
        height: auto;
        margin: 0 1 0 0;
        padding: 0 1 1 1;
        border: solid ansi_blue;
        background: ansi_bright_white;
        color: ansi_black;
    }
    #version_cols .ver_col:last-child {
        margin-right: 0;
    }
    #config_preview {
        color: ansi_black;
        margin-top: 1;
        width: 100%;
        text-style: bold;
    }
    #log {
        height: 1fr;
        width: 100%;
        background: ansi_black;
        color: ansi_bright_white;
        border: solid ansi_black;
        padding: 0 1;
    }
    #bar {
        width: 100%;
        height: 1;
        margin: 0 0 1 0;
        padding: 0 1;
    }
    #bar Bar {
        width: 1fr;
        height: 1;
        color: ansi_green;
        background: ansi_black;
    }
    #body {
        color: ansi_black;
        width: 100%;
        height: auto;
    }
    CompleteScreen DialogBox.page {
        height: auto;
        max-height: 100%;
    }
    CompleteScreen DialogBox.page #dialog_mid {
        height: auto;
    }
    CompleteScreen #content {
        height: auto;
    }
    """
    )


class WizardScreen(Screen):
    """GTK BasePage shape: system status bar / title / content / centered buttons.

    Navigation basis:
      - dialog(1) radiolist: ↑↓ in list; leave list to reach buttons
      - Textual RadioSet: one focus stop per group; arrows inside; Tab between groups
      - Gamepad (MS): D-pad=arrows, A=Enter; 掌机 has no Tab

    Handheld mapping:
      ↑↓  move+select inside current list (dialog: highlight = choice)
      ←→  next/prev list (Textual Tab); single list → jump to #nav buttons
      list bottom ↓ / #nav ↑  list ↔ buttons
      #nav ←→  cycle buttons; Enter activates focused button
      OptionList Enter = connect (Textual default); Esc = back
    """

    BINDINGS = [
        Binding("escape", "go_back", show=False, priority=True),
        # Steal from RadioSet: stock widget only moves cursor, does not select.
        Binding("up", "pad_up", show=False, priority=True),
        Binding("down", "pad_down", show=False, priority=True),
        Binding("left", "pad_left", show=False, priority=True),
        Binding("right", "pad_right", show=False, priority=True),
    ]

    shot_name: str = ""
    step_key: str = ""
    title_text: str = ""
    subtitle_text: str = ""
    nav_spec: Sequence[Tuple[str, str, str]] = (
        ("back", "返回", ""),
        ("next", "继续", "-primary"),
    )
    focus_nav: str = "next"

    def __init__(self) -> None:
        super().__init__()
        self._armed = False

    def compose(self) -> ComposeResult:
        with PageFrame():
            yield SystemStatusBar()
            yield from compose_dialog(
                mode="page",
                title=self.title_text,
                subtitle=self.subtitle_text or None,
                nav_spec=self.nav_spec,
                body=self.compose_content,
            )

    def compose_content(self) -> ComposeResult:
        yield Static("", id="body")

    def on_mount(self) -> None:
        try:
            self.query_one(f"#{self.focus_nav}", Button).focus()
        except Exception:
            pass
        if self.shot_name:
            _capture_when_ready(self, self.shot_name)
        if _sim_auto():
            delay = float(os.environ.get("INSTALLER_SIM_AUTO_DELAY", "0.5"))
            self.set_timer(delay, self._sim_go)

    def on_screen_resume(self) -> None:
        # Returning from a pushed child must re-arm 继续 (otherwise next is dead).
        self._armed = False

    def _radio_value(self, set_id: str, default: str) -> str:
        try:
            rs = self.query_one(f"#{set_id}", RadioSet)
            pressed = rs.pressed_button
            if pressed is None:
                return default
            # ids like mode_fresh / src_online
            bid = str(pressed.id or "")
            if "_" in bid:
                return bid.split("_", 1)[1]
            return bid or default
        except Exception:
            return default

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "back":
            self.action_go_back()
        elif bid == "exit":
            self.app.open_complete(
                "cancelled",
                flow_copy.COMPLETE_CANCEL_SUMMARY,
                "您选择了退出安装",
            )
        elif bid in ("next", "start", "go"):
            if self._armed:
                return
            self._armed = True
            self.on_next()

    def _nav_buttons(self) -> List[Button]:
        try:
            return [
                b
                for b in self.query_one("#nav", Horizontal).query(Button)
                if b.display and not b.disabled
            ]
        except Exception:
            return []

    @staticmethod
    def _is_effectively_shown(widget: object) -> bool:
        """True only if widget and all ancestors are displayed (hidden panels excluded)."""
        node: Optional[object] = widget
        while node is not None:
            if hasattr(node, "display") and not bool(getattr(node, "display")):
                return False
            node = getattr(node, "parent", None)
        return True

    def _content_lists(self) -> List[object]:
        """Visible lists in DOM order (each RadioSet/OptionList = one Textual tab stop)."""
        try:
            content = self.query_one("#content", Vertical)
        except Exception:
            return []
        out: List[object] = []
        for w in content.walk_children(with_self=False):
            if not isinstance(w, (RadioSet, OptionList, Checkbox)):
                continue
            if getattr(w, "disabled", False):
                continue
            if not self._is_effectively_shown(w):
                continue
            out.append(w)
        return out

    def _focus_in_nav(self) -> bool:
        focused = self.focused
        return focused is not None and focused in self._nav_buttons()

    def _list_under_focus(self) -> Optional[object]:
        focused = self.focused
        if focused is None:
            return None
        for sel in self._content_lists():
            if focused is sel:
                return sel
            node: Optional[object] = focused
            while node is not None:
                if node is sel:
                    return sel
                node = getattr(node, "parent", None)
        return None

    def _radio_buttons(self, rs: RadioSet) -> List[RadioButton]:
        return [
            c
            for c in rs.children
            if isinstance(c, RadioButton) and c.display and not c.disabled
        ]

    def _radio_index(self, rs: RadioSet) -> int:
        kids = self._radio_buttons(rs)
        if not kids:
            return 0
        # Prefer pressed: entering a RadioSet must not change 100GB→60GB.
        pressed = rs.pressed_button
        if pressed in kids:
            return kids.index(pressed)  # type: ignore[arg-type]
        sel = getattr(rs, "_selected", None)
        if isinstance(sel, int) and 0 <= sel < len(rs.children):
            child = rs.children[sel]
            if child in kids:
                return kids.index(child)  # type: ignore[arg-type]
        return 0

    def _radio_move_select(self, rs: RadioSet, delta: int) -> bool:
        """Move inside RadioSet and select (dialog radiolist: cursor = choice).

        Returns False if movement would leave the set (caller should change focus).
        """
        kids = self._radio_buttons(rs)
        if not kids:
            return False
        idx = self._radio_index(rs) + delta
        if idx < 0 or idx >= len(kids):
            return False
        btn = kids[idx]
        btn.value = True
        try:
            rs._selected = list(rs.children).index(btn)  # type: ignore[attr-defined]
        except Exception:
            pass
        rs.focus()
        return True

    def _option_move(self, ol: OptionList, delta: int) -> bool:
        idx = ol.highlighted
        if idx is None:
            idx = 0
        nxt = idx + delta
        if nxt < 0 or nxt >= ol.option_count:
            return False
        if delta > 0:
            ol.action_cursor_down()
        else:
            ol.action_cursor_up()
        return True

    def _focus_list(self, sel: object) -> None:
        try:
            sel.focus()  # type: ignore[union-attr]
        except Exception:
            return
        if isinstance(sel, Checkbox):
            return
        if isinstance(sel, RadioSet):
            kids = self._radio_buttons(sel)
            if not kids:
                return
            idx = self._radio_index(sel)
            kids[idx].value = True
            try:
                sel._selected = list(sel.children).index(kids[idx])  # type: ignore[attr-defined]
            except Exception:
                pass

    def _goto_adjacent_list(self, cur: object, delta: int) -> bool:
        """Textual Tab between RadioSets — D-pad edge equivalent for 掌机."""
        lists = self._content_lists()
        if cur not in lists or len(lists) < 2:
            return False
        idx = lists.index(cur) + delta
        if idx < 0 or idx >= len(lists):
            return False
        self._focus_list(lists[idx])
        return True

    def _goto_nav(self, which: str = "primary") -> None:
        buttons = self._nav_buttons()
        if not buttons:
            return
        target = buttons[-1] if which == "primary" else buttons[0]
        target.focus()
        if target.id == "go":
            _announce_page("confirm_go")

    def _pad_vertical(self, delta: int) -> None:
        lists = self._content_lists()
        in_nav = self._focus_in_nav()

        if in_nav:
            if delta < 0 and lists:
                self._focus_list(lists[-1])
            return

        cur = self._list_under_focus()
        if cur is None:
            if lists:
                self._focus_list(lists[0] if delta > 0 else lists[-1])
            return

        if isinstance(cur, RadioSet):
            if self._radio_move_select(cur, delta):
                return
            # Edge of this list → next/prev list (Tab), else nav.
            if self._goto_adjacent_list(cur, delta):
                return
            if delta > 0:
                self._goto_nav("primary")
            return

        if isinstance(cur, OptionList):
            if self._option_move(cur, delta):
                return
            if self._goto_adjacent_list(cur, delta):
                return
            if delta > 0:
                self._goto_nav("primary")
            return

        if isinstance(cur, Checkbox):
            if self._goto_adjacent_list(cur, delta):
                return
            if delta > 0:
                self._goto_nav("primary")

    def _pad_horizontal(self, delta: int) -> None:
        """←→: between lists (Tab), or between #nav buttons — not within a vertical list."""
        in_nav = self._focus_in_nav()
        buttons = self._nav_buttons()
        cur = self._list_under_focus()

        if in_nav and buttons:
            focused = self.focused
            idx = buttons.index(focused)  # type: ignore[arg-type]
            nxt = buttons[(idx + delta) % len(buttons)]
            nxt.focus()
            if nxt.id == "go":
                _announce_page("confirm_go")
            return

        if cur is not None:
            # Prefer jumping to sibling list (version page columns / stacked groups).
            if self._goto_adjacent_list(cur, delta):
                return
            # Single list page: ←→ reach button row (dialog leave-list).
            self._goto_nav("primary" if delta > 0 else "first")
            return

        if buttons:
            self._goto_nav("primary" if delta > 0 else "first")

    def action_pad_up(self) -> None:
        self._pad_vertical(-1)

    def action_pad_down(self) -> None:
        self._pad_vertical(1)

    def action_pad_left(self) -> None:
        self._pad_horizontal(-1)

    def action_pad_right(self) -> None:
        self._pad_horizontal(1)

    def action_go_back(self) -> None:
        # Textual keeps a base Screen under the first push; Welcome is stack[1].
        # Only pop when a later wizard page was pushed (len >= 3).
        if len(self.app.screen_stack) >= 3:
            self.app.pop_screen()
        # Welcome / root: Esc is a no-op (use 打开命令行 / 退出).

    def on_next(self) -> None:
        raise NotImplementedError

    def _sim_go(self) -> None:
        if self.shot_name:
            # Off UI thread: wait for real window screenshot ACK, then advance.
            def _wait_then_click() -> None:
                _wait_page_ack(self.shot_name)

                def click() -> None:
                    try:
                        nav = self.focus_nav
                        at = os.environ.get("INSTALLER_SIM_NAV_AT", "").strip()
                        forced = os.environ.get("INSTALLER_SIM_NAV", "").strip()
                        if forced and (not at or self.shot_name == at):
                            nav = forced
                        btn = self.query_one(f"#{nav}", Button)
                        btn.focus()
                        self.on_button_pressed(Button.Pressed(btn))
                    except Exception:
                        if not self._armed:
                            self._armed = True
                            self.on_next()

                self.app.call_from_thread(click)

            threading.Thread(target=_wait_then_click, daemon=True).start()
            return
        try:
            btn = self.query_one(f"#{self.focus_nav}", Button)
            btn.focus()
            self.on_button_pressed(Button.Pressed(btn))
        except Exception:
            if not self._armed:
                self._armed = True
                self.on_next()


# ---------------------------------------------------------------------------
# Pages — GUI order
# ---------------------------------------------------------------------------


def _welcome_device_name() -> str:
    try:
        r = subprocess.run(
            ["cat", "/sys/devices/virtual/dmi/id/product_name"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return "未知设备"


def _lscpu_field(rows: Sequence[str], *keys: str) -> Optional[str]:
    for ln in rows:
        for key in keys:
            if key in ln and ":" in ln:
                return ln.split(":", 1)[1].strip()
    return None


def _welcome_system_lines() -> List[str]:
    """Mirror GUI _get_system_info rows (CPU / RAM / disks / boot / screen)."""
    lines: List[str] = []
    # Prefer C locale — Chinese lscpu uses 型号名称 / CPU: instead of Model name
    env = {**os.environ, "LC_ALL": "C", "LANG": "C"}
    try:
        cpu = subprocess.run(
            ["lscpu"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            env=env,
        )
        if cpu.returncode == 0:
            rows = cpu.stdout.splitlines()
            model = _lscpu_field(rows, "Model name", "型号名称")
            cores = _lscpu_field(rows, "CPU(s):", "CPU:")
            if model and cores:
                if len(model) > 40:
                    model = model[:37] + "..."
                lines.append(f"CPU: {model} ({cores} 核心)")
    except Exception:
        pass
    try:
        mem = subprocess.run(
            ["free", "-h"], capture_output=True, text=True, timeout=1, check=False
        )
        if mem.returncode == 0:
            total = mem.stdout.splitlines()[1].split()[1]
            lines.append(f"内存: {total}")
    except Exception:
        pass
    try:
        disks = subprocess.run(
            ["lsblk", "-dno", "NAME,TYPE"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        if disks.returncode == 0:
            n = sum(
                1
                for ln in disks.stdout.splitlines()
                if ln.strip().endswith("disk")
            )
            lines.append(f"检测到 {n} 个磁盘")
    except Exception:
        pass
    boot = "UEFI" if Path("/sys/firmware/efi").exists() else "Legacy BIOS"
    lines.append(f"引导模式: {boot}")
    try:
        import shutil

        cols, rows = shutil.get_terminal_size(fallback=(80, 24))
        lines.append(f"屏幕: 终端 {cols}x{rows}")
    except Exception:
        pass
    if not lines:
        lines = [
            "系统信息暂不可用",
            "仍可继续安装流程",
        ]
    # Align labels like a small info table
    return [f"  {ln}" for ln in lines]


# Plain text only — box-drawing + card border draws a double/ghost frame.
_WELCOME_LOGO = "SKORION"


class WelcomeScreen(WizardScreen):
    """GUI create_welcome_page: status → logo/title/device/info → buttons under card."""

    shot_name = "welcome"
    step_key = "welcome"
    title_text = "SkorionOS 安装器"
    subtitle_text = f"版本 {VERSION}"
    nav_spec = (("exit", "打开命令行", ""), ("start", "开始安装", "-primary"))
    focus_nav = "start"

    def compose(self) -> ComposeResult:
        device = _welcome_device_name()
        info = "\n".join(_welcome_system_lines())

        def body() -> ComposeResult:
            yield Static(_WELCOME_LOGO, id="welcome_logo")
            yield Rule(line_style="heavy", id="welcome_rule")
            yield Label(self.title_text, id="title")
            yield Label(self.subtitle_text, id="subtitle")
            yield Static(f"检测到设备: {device}", id="welcome_device")
            yield Static(info, id="welcome_info")

        with PageFrame():
            yield SystemStatusBar()
            yield from compose_dialog(
                mode="compact",
                title=None,
                subtitle=None,
                nav_spec=self.nav_spec,
                body=body,
                panel_classes="welcome",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "exit":
            self.app.exit()
            return
        super().on_button_pressed(event)

    def on_next(self) -> None:
        self.app.push_screen(NetworkScreen())

class WifiPasswordScreen(Screen):
    """WiFi password — gamepad D-pad, no Tab (掌机)."""

    BINDINGS = [
        Binding("escape", "cancel", show=False, priority=True),
        Binding("up", "pad_up", show=False, priority=True),
        Binding("down", "pad_down", show=False, priority=True),
        Binding("left", "pad_left", show=False, priority=True),
        Binding("right", "pad_right", show=False, priority=True),
    ]

    def __init__(self, net: WifiNetwork, wifi: WifiService) -> None:
        super().__init__()
        self._net = net
        self._wifi = wifi
        self._busy = False

    def compose(self) -> ComposeResult:
        def body() -> ComposeResult:
            yield Static(
                "输入密码 · ↓/←→ 到按钮 · Enter 连接 · Esc 取消",
                id="wifi_hint",
            )
            yield Input(
                placeholder="密码",
                password=True,
                id="wifi_password",
            )
            yield Static("", id="wifi_status")

        with PageFrame():
            yield SystemStatusBar()
            yield from compose_dialog(
                mode="page",
                title="输入 WiFi 密码",
                subtitle=f"网络: {self._net.ssid}",
                nav_spec=(
                    ("cancel", "取消", ""),
                    ("connect", "连接", "-primary"),
                ),
                body=body,
            )

    def on_mount(self) -> None:
        self.query_one("#wifi_password", Input).focus()
        if _sim_auto():
            _capture_when_ready(self, "wifi_password")
            delay = float(os.environ.get("INSTALLER_SIM_AUTO_DELAY", "0.5"))

            def go() -> None:
                def worker() -> None:
                    _wait_page_ack("wifi_password")

                    def cancel() -> None:
                        try:
                            self.app.pop_screen()
                        except Exception:
                            pass

                    self.app.call_from_thread(cancel)

                threading.Thread(target=worker, daemon=True).start()

            self.set_timer(delay, go)

    def _focusables(self) -> List[object]:
        inp = self.query_one("#wifi_password", Input)
        cancel = self.query_one("#cancel", Button)
        connect = self.query_one("#connect", Button)
        return [inp, cancel, connect]

    def _pad_step(self, delta: int) -> None:
        items = self._focusables()
        focused = self.focused
        try:
            idx = items.index(focused)  # type: ignore[arg-type]
        except ValueError:
            idx = 0
        nxt = items[(idx + delta) % len(items)]
        try:
            nxt.focus()  # type: ignore[union-attr]
        except Exception:
            pass

    def action_pad_up(self) -> None:
        # From buttons → password; from password stay.
        if isinstance(self.focused, Button):
            self.query_one("#wifi_password", Input).focus()

    def action_pad_down(self) -> None:
        if isinstance(self.focused, Input):
            self.query_one("#connect", Button).focus()
        elif self.focused is not None and self.focused.id == "cancel":
            self.query_one("#connect", Button).focus()

    def action_pad_left(self) -> None:
        if isinstance(self.focused, Input):
            # Don't steal caret moves for empty field; jump to 取消 when empty.
            inp = self.query_one("#wifi_password", Input)
            if not inp.value:
                self.query_one("#cancel", Button).focus()
            return
        self._pad_step(-1)

    def action_pad_right(self) -> None:
        if isinstance(self.focused, Input):
            inp = self.query_one("#wifi_password", Input)
            if not inp.value:
                self.query_one("#connect", Button).focus()
            return
        self._pad_step(1)

    def action_cancel(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.action_cancel()
        elif event.button.id == "connect":
            self._do_connect()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "wifi_password":
            self._do_connect()

    def _do_connect(self) -> None:
        if self._busy:
            return
        password = self.query_one("#wifi_password", Input).value or ""
        if self._net.secured and not password:
            self.query_one("#wifi_status", Static).update("[bold red]请输入密码[/]")
            return
        self._busy = True
        self.query_one("#wifi_status", Static).update("正在连接…")
        self.query_one("#connect", Button).disabled = True

        def done(ok: bool, err: Optional[str], ssid: str) -> None:
            def ui() -> None:
                self._busy = False
                try:
                    self.query_one("#connect", Button).disabled = False
                except Exception:
                    pass
                if ok:
                    self.app.pop_screen()
                    try:
                        net = self.app.screen
                        if isinstance(net, NetworkScreen):
                            net.reload_networks(announce=False, focus_next=True)
                    except Exception:
                        pass
                else:
                    self.query_one("#wifi_status", Static).update(
                        f"[bold red]{err or '连接失败'}[/]"
                    )
                    self.query_one("#wifi_password", Input).focus()

            self.app.call_from_thread(ui)

        self._wifi.connect(self._net, password, done)


class NetworkScreen(WizardScreen):
    """GUI network page: WiFi OptionList + NM/nmcli/sim connect (keyboard only)."""

    shot_name = "network"
    step_key = "network"
    title_text = "网络连接"
    subtitle_text = "↑↓ 选网 · ←→ 底栏 · Enter 连接/继续"
    focus_nav = "next"

    def __init__(self) -> None:
        self._wifi = WifiService()
        self._networks: List[WifiNetwork] = []
        self._online = self._wifi.is_online()
        self._rebuild_nav()
        super().__init__()

    def _rebuild_nav(self) -> None:
        # Stable button set so every control stays reachable after online/offline flips.
        online = self._online
        self.nav_spec = (
            ("back", "返回", ""),
            ("refresh", "刷新", ""),
            ("connect", "重新连接" if online else "连接", ""),
            ("disconnect", "断开", ""),
            ("next", "继续" if online else "跳过", "-primary"),
        )

    def compose_content(self) -> ComposeResult:
        yield Static("", id="wifi_status")
        yield Static(
            "↑↓ 选网 · 列表 Enter=连接 · ↓到底/←→ 底栏 · Enter=继续",
            id="wifi_hint",
        )
        yield OptionList(id="wifi_list")

    def on_mount(self) -> None:
        self.reload_networks(announce=True, focus_next=True)
        super().on_mount()

    def _sim_go(self) -> None:
        if os.environ.get("INSTALLER_SIM_WIFI", "") in ("1", "true", "yes"):
            def worker() -> None:
                _wait_page_ack("network")

                def click() -> None:
                    try:
                        ol = self.query_one("#wifi_list", OptionList)
                        for i, net in enumerate(self._networks):
                            if net.secured:
                                ol.highlighted = i
                                break
                        self._start_connect()
                    except Exception:
                        super(NetworkScreen, self)._sim_go()

                self.app.call_from_thread(click)

            threading.Thread(target=worker, daemon=True).start()
            return
        super()._sim_go()

    def reload_networks(self, announce: bool = False, focus_next: bool = False) -> None:
        self._networks = self._wifi.scan()
        self._online = self._wifi.is_online()
        ssid = self._wifi.connected_ssid()
        if self._online:
            status = "[bold]网络已连接，可以继续安装[/]"
            if ssid:
                status += f"\n当前连接: {ssid}"
        else:
            status = (
                "[bold yellow]未检测到网络连接[/]\n"
                "选择下方 WiFi 后按「连接」（或 Enter）。"
            )
        try:
            self.query_one("#wifi_status", Static).update(status)
        except Exception:
            pass
        ol = self.query_one("#wifi_list", OptionList)
        ol.clear_options()
        if not self._networks:
            ol.add_option(Option("未找到可用网络 — 按「刷新」重试", id="wifi_none", disabled=True))
        else:
            for i, n in enumerate(self._networks):
                lock = "*" if n.secured else " "
                mark = "+" if n.connected else " "
                label = f"{mark}{lock} {n.ssid}  {n.strength}%  {n.band}"
                ol.add_option(Option(label, id=f"wifi_{i}"))
            ol.highlighted = 0
        try:
            nxt = self.query_one("#next", Button)
            nxt.label = "继续" if self._online else "跳过"
            conn = self.query_one("#connect", Button)
            conn.label = "重新连接" if self._online else "连接"
            disc = self.query_one("#disconnect", Button)
            disc.disabled = not self._online
        except Exception:
            pass
        if focus_next:
            try:
                self.query_one("#next", Button).focus()
            except Exception:
                pass
        if announce:
            _announce_page("network")

    def _selected_network(self) -> Optional[WifiNetwork]:
        ol = self.query_one("#wifi_list", OptionList)
        idx = ol.highlighted
        if idx is None or idx < 0 or idx >= len(self._networks):
            return None
        return self._networks[idx]

    def _start_connect(self) -> None:
        net = self._selected_network()
        if net is None:
            self.query_one("#wifi_status", Static).update(
                "[bold red]请先用 ↑↓ 选择一个 WiFi 网络[/]"
            )
            self.query_one("#wifi_list", OptionList).focus()
            return
        if net.band == "ETH" or net.ssid.startswith("有线"):
            self.query_one("#wifi_status", Static).update("有线网络已连接。")
            return
        if net.secured:
            self.app.push_screen(WifiPasswordScreen(net, self._wifi))
            return
        self.query_one("#wifi_status", Static).update(f"正在连接 {net.ssid}…")

        def done(ok: bool, err: Optional[str], ssid: str) -> None:
            def ui() -> None:
                if ok:
                    # Return focus to 继续 so Enter advances (list Enter stays = connect).
                    self.reload_networks(announce=False, focus_next=True)
                else:
                    self.query_one("#wifi_status", Static).update(
                        f"[bold red]{err or '连接失败'}[/]"
                    )

            self.app.call_from_thread(ui)

        self._wifi.connect(net, "", done)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "wifi_list":
            self._start_connect()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "refresh":
            self.reload_networks(announce=False, focus_next=False)
            self.query_one("#wifi_list", OptionList).focus()
            return
        if bid == "connect":
            self._start_connect()
            return
        if bid == "disconnect":
            ssid = self._wifi.connected_ssid()
            if not ssid:
                self.query_one("#wifi_status", Static).update("当前没有 WiFi 连接可断开。")
                return

            def done(ok: bool, result_ssid: str) -> None:
                def ui() -> None:
                    self.reload_networks(announce=False, focus_next=True)

                self.app.call_from_thread(ui)

            self._wifi.disconnect(ssid, done)
            return
        super().on_button_pressed(event)

    def on_next(self) -> None:
        self.app.push_screen(DiskScreen())


class DiskScreen(WizardScreen):
    shot_name = "disk"
    step_key = "disk"
    title_text = "磁盘选择"
    subtitle_text = "请选择要安装 SkorionOS 的磁盘"
    # GUI disk.py: 返回 / 继续 only (no 退出)
    focus_nav = "next"

    def __init__(self) -> None:
        self._disks = list_disks()
        super().__init__()

    def compose_content(self) -> ComposeResult:
        if not self._disks:
            yield Static("未找到可安装磁盘（请连接 ≥64GB 磁盘后重试）", id="body")
            return
        with RadioSet(id="disk_set"):
            for i, (name, desc) in enumerate(self._disks):
                yield RadioButton(
                    f"/dev/{name}  —  {desc}",
                    id=f"disk_{name}",
                    value=(i == 0),
                )

    def on_mount(self) -> None:
        super().on_mount()
        self._sync_disk_to_plan()

        def focus_disks() -> None:
            try:
                self.query_one("#disk_set", RadioSet).focus()
            except Exception:
                pass

        focus_disks()
        # Super focuses #next; keep list focused after refresh (arrow/keyboard UX).
        self.call_after_refresh(focus_disks)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self._sync_disk_to_plan()

    def _sync_disk_to_plan(self) -> None:
        tag = self._radio_value("disk_set", "")
        if tag and tag != "none":
            self.app.plan.disk = tag

    def on_next(self) -> None:
        tag = self._radio_value("disk_set", "")
        if not tag:
            self._armed = False
            return
        self.app.plan.disk = tag
        gate = after_disk_selected(tag)
        self._route_disk_gate(gate)

    def _route_disk_gate(self, gate) -> None:
        self.app.has_existing_installation = gate.has_existing
        disk = self.app.plan.disk_name()
        if gate.step == "too_small":
            self.app.push_screen(ProductMessageScreen("too_small", disk))
        elif gate.step == "external":
            self.app.push_screen(ProductMessageScreen("external", disk))
        elif gate.step == "incomplete":
            self.app.push_screen(ProductMessageScreen("incomplete", disk))
        else:
            self.app.push_screen(ModeScreen())


class ProductMessageScreen(WizardScreen):
    """Disk safety / incomplete-frzr copy from installer.flow.copy."""

    shot_name = "message"
    step_key = "message"

    def __init__(self, step: str, disk: str) -> None:
        self.step = step
        self.disk = disk
        min_gb = flow_copy.MIN_DISK_GB
        if step == "too_small":
            self.title_text = flow_copy.DISK_TOO_SMALL_TITLE
            self.subtitle_text = ""
            self.nav_spec = (("back", flow_copy.BTN_BACK, ""),)
            self.focus_nav = "back"
            self._body = (
                flow_copy.DISK_TOO_SMALL_MSG.format(disk=disk, min_gb=min_gb)
                + "\n\n"
                + flow_copy.DISK_TOO_SMALL_DETAIL
            )
        elif step == "external":
            self.title_text = flow_copy.EXTERNAL_TITLE
            self.subtitle_text = ""
            self.nav_spec = (
                ("back", flow_copy.BTN_BACK, ""),
                ("next", flow_copy.BTN_CONTINUE, "-primary"),
            )
            self.focus_nav = "next"
            self._body = flow_copy.EXTERNAL_MSG.format(disk=disk) + "\n\n" + flow_copy.EXTERNAL_DETAILS
        elif step == "incomplete":
            self.title_text = flow_copy.INCOMPLETE_TITLE
            self.subtitle_text = ""
            self.nav_spec = (
                ("back", flow_copy.BTN_BACK, ""),
                ("next", flow_copy.BTN_CLEANUP, "-primary"),
            )
            self.focus_nav = "next"
            self._body = (
                flow_copy.INCOMPLETE_MSG.format(disk=disk) + "\n\n" + flow_copy.INCOMPLETE_DETAILS
            )
        elif step == "no_shrink":
            self.title_text = flow_copy.NO_SHRINK_PART_TITLE
            self.subtitle_text = ""
            self.nav_spec = (("back", flow_copy.BTN_BACK, ""),)
            self.focus_nav = "back"
            self._body = flow_copy.NO_SHRINK_PART_MSG
        else:
            self.title_text = flow_copy.NETWORK_OFFLINE_TITLE
            self.subtitle_text = ""
            self.nav_spec = (("back", flow_copy.BTN_BACK, ""),)
            self.focus_nav = "back"
            self._body = (
                flow_copy.NETWORK_OFFLINE_MSG + "\n\n" + flow_copy.NETWORK_OFFLINE_DETAIL
            )
        super().__init__()

    def compose_content(self) -> ComposeResult:
        yield Static(self._body, id="body")

    def on_next(self) -> None:
        if self.step == "too_small" or self.step in ("no_shrink", "offline"):
            self._armed = False
            return
        if self.step == "external":
            gate = after_frzr_check(self.disk)
            self.app.has_existing_installation = gate.has_existing
            if gate.step == "incomplete":
                self.app.push_screen(ProductMessageScreen("incomplete", self.disk))
            else:
                self.app.push_screen(ModeScreen())
            return
        self.app.has_existing_installation = False
        self.app.push_screen(ModeScreen())


class ModeScreen(WizardScreen):
    shot_name = "mode"
    step_key = "mode"
    title_text = flow_copy.MODE_TITLE
    subtitle_text = flow_copy.MODE_SUBTITLE
    # Match GUI (no existing install): 返回 / 退出 / 继续
    nav_spec = (
        ("back", flow_copy.BTN_BACK, ""),
        ("exit", flow_copy.BTN_EXIT, ""),
        ("next", flow_copy.BTN_CONTINUE, "-primary"),
    )
    focus_nav = "next"

    def compose_content(self) -> ComposeResult:
        existing = bool(getattr(self.app, "has_existing_installation", False))
        with RadioSet(id="mode_set"):
            if existing:
                yield RadioButton(
                    f"{flow_copy.MODE_REPAIR} — {flow_copy.MODE_REPAIR_DESC}",
                    id="mode_repair",
                    value=True,
                )
                yield RadioButton(
                    f"{flow_copy.MODE_FRESH_EXISTING} — {flow_copy.MODE_FRESH_EXISTING_DESC}",
                    id="mode_fresh",
                )
                yield RadioButton(
                    f"{flow_copy.MODE_DUAL_EXISTING} — {flow_copy.MODE_DUAL_EXISTING_DESC}",
                    id="mode_dual",
                )
            else:
                yield RadioButton(
                    f"{flow_copy.MODE_FRESH} — {flow_copy.MODE_FRESH_DESC}",
                    id="mode_fresh",
                    value=True,
                )
                yield RadioButton(
                    f"{flow_copy.MODE_DUAL} — {flow_copy.MODE_DUAL_DESC}",
                    id="mode_dual",
                )

    def on_mount(self) -> None:
        if getattr(self.app, "has_existing_installation", False):
            try:
                disk = self.app.plan.disk_name()
                self.query_one("#title", Label).update(flow_copy.MODE_TITLE_EXISTING)
                self.query_one("#subtitle", Label).update(
                    flow_copy.MODE_SUBTITLE_EXISTING.format(disk=disk)
                )
            except Exception:
                pass
        super().on_mount()

        def focus_modes() -> None:
            try:
                self.query_one("#mode_set", RadioSet).focus()
            except Exception:
                pass

        focus_modes()
        self.call_after_refresh(focus_modes)
        forced = os.environ.get("INSTALLER_SIM_MODE", "").strip()
        if forced in ("repair", "fresh", "dual"):
            try:
                self.query_one(f"#mode_{forced}", RadioButton).value = True
            except Exception:
                pass

    def on_next(self) -> None:
        tag = self._radio_value("mode_set", "fresh")
        self.app.plan.mode = tag  # type: ignore[assignment]
        if tag == "dual":
            dual = after_dual_selected(self.app.plan.disk_name())
            if dual.step == "confirm_auto":
                self.app.plan.dual_op = "auto"
                self.app.push_screen(ConfirmScreen())
            else:
                self.app.push_screen(PartitionAdjustScreen())
        else:
            self.app.plan.dual_op = None
            self.app.push_screen(ConfirmScreen())


class PartitionAdjustScreen(WizardScreen):
    shot_name = "partition_adjust"
    step_key = "partition_adjust"
    title_text = "磁盘空间不足"
    subtitle_text = "↑↓ 选择操作 · ↓到底栏 · ←→ 切换按钮"
    nav_spec = (
        ("back", flow_copy.BTN_BACK, ""),
        ("exit", flow_copy.BTN_EXIT, ""),
        ("next", flow_copy.BTN_CONTINUE, "-primary"),
    )
    focus_nav = "next"

    def compose_content(self) -> ComposeResult:
        disk = ""
        try:
            disk = self.app.plan.disk_name()
        except Exception:
            disk = ""
        self._parts = shrinkable_partitions(disk) if disk else []
        if self._parts:
            yield Label("选择分区", classes="section-label")
            with RadioSet(id="part_set"):
                for i, part in enumerate(self._parts):
                    fstype = part.get("fstype", "")
                    size = part.get("size_gb", "")
                    yield RadioButton(
                        f"{part['path']}  —  {fstype} {size}GB",
                        id=f"part_{i}",
                        value=(i == 0),
                    )
        yield Label("选择操作", classes="section-label")
        with RadioSet(id="dual_set"):
            # GUI partition_adjust: shrink/delete only (auto is a different page).
            yield RadioButton("缩小分区", id="dual_shrink", value=True)
            yield RadioButton("删除整个分区", id="dual_delete")
        yield Label("释放空间", classes="section-label")
        with RadioSet(id="size_set"):
            yield RadioButton("60GB — 最小推荐", id="size_60")
            yield RadioButton("100GB — 推荐配置", id="size_100", value=True)
            yield RadioButton("200GB — 充足空间", id="size_200")

    def on_mount(self) -> None:
        super().on_mount()

        def focus_ops() -> None:
            try:
                self.query_one("#dual_set", RadioSet).focus()
            except Exception:
                pass

        # Same as DiskScreen: options must be focused or ↑↓ never reaches them.
        focus_ops()
        self.call_after_refresh(focus_ops)
        forced_dual = os.environ.get("INSTALLER_SIM_DUAL", "").strip()
        if forced_dual == "delete":
            try:
                self.query_one("#dual_delete", RadioButton).value = True
            except Exception:
                pass

    def on_next(self) -> None:
        tag = self._radio_value("dual_set", "shrink")
        plan = self.app.plan
        plan.dual_op = tag  # type: ignore[assignment]
        disk = plan.disk_name()
        parts = list(getattr(self, "_parts", None) or shrinkable_partitions(disk))
        if tag in ("shrink", "delete") and not parts:
            self.app.push_screen(ProductMessageScreen("no_shrink", disk))
            return
        idx = 0
        try:
            idx = int(self._radio_value("part_set", "0"))
        except Exception:
            idx = 0
        part = parts[idx]["path"] if parts and 0 <= idx < len(parts) else (
            parts[0]["path"] if parts else None
        )
        if tag == "shrink":
            plan.shrink_partition = part
            try:
                plan.shrink_size_gb = int(self._radio_value("size_set", "100"))
            except Exception:
                plan.shrink_size_gb = 100
            plan.delete_partition = None
        elif tag == "delete":
            plan.delete_partition = part
            plan.shrink_partition = None
            plan.shrink_size_gb = None
        else:
            plan.shrink_partition = None
            plan.shrink_size_gb = None
            plan.delete_partition = None
        self.app.push_screen(ConfirmScreen())


class ConfirmScreen(WizardScreen):
    shot_name = "confirm"
    step_key = "confirm"
    title_text = "确认安装"
    subtitle_text = ""
    nav_spec = (
        ("back", "返回", ""),
        ("exit", "退出", ""),
        ("go", "继续", "-primary"),
    )
    focus_nav = "go"

    def compose_content(self) -> ComposeResult:
        # Copy aligned with GUI confirm.py
        p = self.app.plan
        mode = MODE_CN.get(p.mode, p.mode)
        if p.mode == "fresh":
            details = (
                f"[bold]{mode}[/]\n"
                f"磁盘: {p.disk_path()}\n\n"
                "此操作将：\n"
                "• 格式化整个磁盘\n"
                "• 删除所有现有分区和数据\n"
                "• 创建新的系统分区\n\n"
                "[bold red]警告: 磁盘上的所有数据将被永久删除！[/]\n\n"
                "您是否要继续？"
            )
        elif p.mode == "repair":
            details = (
                f"[bold]{mode}[/]\n"
                f"磁盘: {p.disk_path()}\n\n"
                "此操作将：\n"
                "• 保留用户数据（/home、/var）\n"
                "• 重装引导加载器\n"
                "• 清理系统部署\n\n"
                "您是否要继续？"
            )
        else:
            dual_op = p.dual_op or "auto"
            if dual_op == "shrink":
                details = (
                    f"[bold]双系统安装 - 缩小分区[/]\n"
                    f"磁盘: {p.disk_path()}\n\n"
                    f"[bold yellow]将缩小分区: {p.shrink_partition or '未知'}[/]\n"
                    f"释放空间: {p.shrink_size_gb or 0} GB\n\n"
                    "[bold red]警告: 此操作有风险，请确保已备份重要数据！[/]\n\n"
                    "您是否要继续？"
                )
            elif dual_op == "delete":
                details = (
                    f"[bold]双系统安装 - 删除分区[/]\n"
                    f"磁盘: {p.disk_path()}\n\n"
                    f"[bold red]警告: 将删除分区 {p.delete_partition or '未知'}！[/]\n"
                    "[bold red]该分区上的所有数据将永久丢失！[/]\n\n"
                    "您是否要继续？"
                )
            else:
                details = (
                    f"[bold]{mode}[/]\n"
                    f"磁盘: {p.disk_path()}\n\n"
                    "将使用磁盘上的未分配空间创建分区\n"
                    "现有系统将被保留\n\n"
                    "您是否要继续？"
                )
        yield Static(details, id="body")

    def on_mount(self) -> None:
        def focus_back() -> None:
            try:
                self.query_one("#back", Button).focus()  # cautious default like GUI
            except Exception:
                pass

        focus_back()
        self.call_after_refresh(focus_back)
        _capture_when_ready(self, "confirm")
        if _sim_auto():
            delay = float(os.environ.get("INSTALLER_SIM_AUTO_DELAY", "0.5"))

            def go() -> None:
                def worker() -> None:
                    _wait_page_ack("confirm")

                    def focus_go() -> None:
                        if os.environ.get("INSTALLER_SIM_CONFIRM_BACK", "") in (
                            "1",
                            "true",
                            "yes",
                        ):
                            os.environ["INSTALLER_SIM_CONFIRM_BACK"] = "0"
                            btn = self.query_one("#back", Button)
                            btn.focus()
                            self.on_button_pressed(Button.Pressed(btn))
                            return
                        btn = self.query_one("#go", Button)
                        btn.focus()
                        _capture_when_ready(self, "confirm_go")

                        def after_go_shot() -> None:
                            def w2() -> None:
                                _wait_page_ack("confirm_go")
                                self.app.call_from_thread(
                                    lambda: self.on_button_pressed(Button.Pressed(btn))
                                )

                            threading.Thread(target=w2, daemon=True).start()

                        self.set_timer(0.85, after_go_shot)

                    self.app.call_from_thread(focus_go)

                threading.Thread(target=worker, daemon=True).start()

            self.set_timer(delay, go)

    def _sim_go(self) -> None:
        # WizardScreen._sim_go would press #go as soon as "confirm" is ACKed,
        # racing the confirm_go shot. SIM_AUTO for this page is on_mount above.
        return

    def on_next(self) -> None:
        self.app.push_screen(BootstrapScreen())


class ExecutionScreen(Screen):
    """GTK ExecutionPage: status + ProgressBar + log + Button."""

    BINDINGS = [Binding("escape", "noop", show=False)]
    shot_name: str = ""
    title_text: str = ""
    initial_status: str = "准备中…"
    service_name: str = ""

    def compose(self) -> ComposeResult:
        def body() -> ComposeResult:
            yield ProgressBar(total=100, show_eta=False, id="bar")
            yield Static("", id="log")

        with PageFrame():
            yield SystemStatusBar()
            yield from compose_dialog(
                mode="page",
                title=self.title_text,
                subtitle=self.initial_status,
                nav_spec=(
                    ("exit", "取消", ""),
                    ("next", "继续", "-primary"),
                ),
                body=body,
            )

    def on_key(self, event: events.Key) -> None:
        if event.key not in ("left", "right"):
            return
        try:
            buttons = [
                b
                for b in self.query_one("#nav", Horizontal).query(Button)
                if b.display and not b.disabled
            ]
        except Exception:
            return
        if len(buttons) < 2:
            return
        focused = self.focused
        if focused not in buttons:
            return
        idx = buttons.index(focused)  # type: ignore[arg-type]
        delta = -1 if event.key == "left" else 1
        buttons[(idx + delta) % len(buttons)].focus()
        event.stop()

    def on_mount(self) -> None:
        try:
            self.query_one("#next", Button).disabled = True
        except Exception:
            pass
        self._lines: List[str] = []
        self._ready = False
        self._ok = False
        _capture_when_ready(self, self.shot_name)

        def start_after_shot() -> None:
            _wait_page_ack(self.shot_name)
            threading.Thread(target=self._run, daemon=True).start()

        self.set_timer(
            0.15, lambda: threading.Thread(target=start_after_shot, daemon=True).start()
        )

    def action_noop(self) -> None:
        return

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "exit":
            self.app.open_complete(
                "cancelled",
                flow_copy.COMPLETE_CANCEL_SUMMARY,
                "安装已取消",
            )
        elif event.button.id == "next" and self._ready and self._ok:
            self.on_next()

    def _append(self, text: str) -> None:
        line = text.rstrip("\n")
        if not line:
            return
        self._lines.append(line)
        self.query_one("#log", Static).update("\n".join(self._lines[-14:]))

    def _emit(self, event: ProgressEvent) -> None:
        def ui() -> None:
            bar = self.query_one("#bar", ProgressBar)
            sub = self.query_one("#subtitle", Label)
            if event.kind == EventKind.LOG:
                self._append(event.message)
            elif event.kind == EventKind.STAGE:
                msg = event.message or event.stage
                sub.update(msg)
                self._append(msg)
                try:
                    bar.advance(8)
                except Exception:
                    pass
            elif event.kind == EventKind.FINISHED:
                self._ready = True
                self._ok = bool(event.ok)
                nxt = self.query_one("#next", Button)
                if event.ok:
                    self.query_one("#title", Label).update(self.title_text)
                    sub.update("已完成，请点击「继续」")
                    bar.update(progress=100)
                    nxt.disabled = False
                    nxt.focus()
                else:
                    self.query_one("#title", Label).update(self.title_text)
                    sub.update(event.error or "执行失败，请查看下方日志")
                    nxt.disabled = True
                    self.app.open_complete(
                        "failed",
                        flow_copy.COMPLETE_FAIL_SUMMARY,
                        event.error or "",
                    )
                done_label = f"{self.service_name}_done"
                _capture_when_ready(self, done_label)
                if _sim_auto() and event.ok:
                    def advance() -> None:
                        _wait_page_ack(done_label)
                        self.app.call_from_thread(self.on_next)

                    threading.Thread(target=advance, daemon=True).start()

        self.app.call_from_thread(ui)

    def _run(self) -> None:
        raise NotImplementedError

    def on_next(self) -> None:
        raise NotImplementedError


class BootstrapScreen(ExecutionScreen):
    shot_name = "bootstrap"
    title_text = "正在初始化磁盘"
    initial_status = "正在格式化磁盘并创建分区…"
    service_name = "bootstrap"

    def _run(self) -> None:
        plan: InstallPlan = self.app.plan
        log_file = installer_log_file()

        def on_event(event: ProgressEvent) -> None:
            if event.kind == EventKind.FINISHED:
                return
            self._emit(event)

        result = BootstrapService(on_event=on_event).run(plan, log_file=log_file)
        if result.returncode != 0:
            self._emit(
                ProgressEvent.finished(False, error=f"bootstrap 失败 ({result.returncode})")
            )
        else:
            after_bootstrap_success(self.app)
            self._emit(ProgressEvent.finished(True))

    def on_next(self) -> None:
        self.app.push_screen(VersionScreen())


class VersionScreen(WizardScreen):
    """GUI version.py: online (3 cols) or local (file list)."""

    shot_name = "version"
    step_key = "version"
    title_text = "版本选择"
    subtitle_text = "↑↓ 选当前列 · ←→ 切换列 · ↓到底栏 Enter 开始"
    nav_spec = (
        ("back", "返回", ""),
        ("exit", "退出", ""),
        ("next", "开始安装", "-primary"),
    )
    focus_nav = "next"

    def compose_content(self) -> ComposeResult:
        files = getattr(self.app, "local_frzr_files", []) or []
        has_local = bool(files)
        net_ok = WifiService().is_online()

        yield Label("安装方式", classes="section-label")
        with RadioSet(id="source_set"):
            yield RadioButton(
                "在线安装",
                id="src_online",
                value=net_ok,
                disabled=not net_ok,
            )
            yield RadioButton(
                "本地安装",
                id="src_local",
                value=(not net_ok and has_local),
                disabled=not has_local,
            )
        yield Static("当前配置: stable:gnome", id="config_preview")

        with Vertical(id="online_panel"):
            with Horizontal(id="version_cols"):
                with Vertical(classes="ver_col"):
                    yield Label("版本通道", classes="section-label")
                    with RadioSet(id="channel_set"):
                        yield RadioButton(
                            "稳定版 — 推荐日常使用", id="ch_stable", value=True
                        )
                        yield RadioButton("测试版 — 较新功能", id="ch_testing")
                        yield RadioButton("不稳定版 — 开发测试", id="ch_unstable")
                with Vertical(classes="ver_col"):
                    yield Label("桌面环境", classes="section-label")
                    with RadioSet(id="desktop_set"):
                        yield RadioButton("GNOME — 默认推荐", id="de_gnome", value=True)
                        yield RadioButton(
                            "KDE Plasma — 类似 Steam Deck", id="de_kde"
                        )
                with Vertical(classes="ver_col"):
                    yield Label("NVIDIA 驱动", classes="section-label")
                    with RadioSet(id="nvidia_set"):
                        yield RadioButton("标准版 — 开源驱动", id="nv_no", value=True)
                        yield RadioButton(
                            "NV 版 — 含 NVIDIA 专有驱动", id="nv_yes"
                        )

        with Vertical(id="local_panel"):
            if has_local:
                yield Label("选择镜像文件", classes="section-label")
                with RadioSet(id="local_file_set"):
                    for i, f in enumerate(files):
                        yield RadioButton(
                            f"{f['filename']}  |  {f['device']}  |  {f['size']}",
                            id=f"lf_{i}",
                            value=(i == 0),
                        )
            else:
                yield Static(
                    "未找到本地镜像文件\n请插入包含安装镜像的 USB 设备",
                    id="local_empty",
                )
        yield ProductCheckbox(flow_copy.ADVANCED_ENABLE, id="opt_advanced", value=False)

    def on_mount(self) -> None:
        src = "online" if WifiService().is_online() else "local"
        self._apply_source_ui(src)
        self._refresh_preview()
        super().on_mount()

        def focus_source() -> None:
            try:
                self.query_one("#source_set", RadioSet).focus()
            except Exception:
                pass

        focus_source()
        self.call_after_refresh(focus_source)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "source_set":
            src = self._radio_value("source_set", "online")
            self._apply_source_ui(src)
            if src == "local":
                _announce_page("version_local")
                # Skip hidden online columns — jump straight to file list.
                self.call_after_refresh(self._focus_local_files)
            elif src == "online":
                self.call_after_refresh(self._focus_online_channel)
        self._refresh_preview()

    def _focus_local_files(self) -> None:
        try:
            self.query_one("#local_file_set", RadioSet).focus()
        except Exception:
            pass

    def _focus_online_channel(self) -> None:
        try:
            self.query_one("#channel_set", RadioSet).focus()
        except Exception:
            pass

    def _apply_source_ui(self, src: str) -> None:
        try:
            online = self.query_one("#online_panel", Vertical)
            local = self.query_one("#local_panel", Vertical)
            online.display = src != "local"
            local.display = src == "local"
        except Exception:
            pass

    def _refresh_preview(self) -> None:
        src = self._radio_value("source_set", "online")
        if src == "local":
            files = getattr(self.app, "local_frzr_files", []) or []
            idx = 0
            try:
                tag = self._radio_value("local_file_set", "0")
                idx = int(tag)
            except Exception:
                idx = 0
            if files and 0 <= idx < len(files):
                text = f"当前配置: 本地镜像: {files[idx]['filename']}"
            else:
                text = "当前配置: 本地安装 (未选择文件)"
        else:
            ch = self._radio_value("channel_set", "stable")
            de = self._radio_value("desktop_set", "gnome")
            nv = self._radio_value("nvidia_set", "no") == "yes"
            text = f"当前配置: {ch}:{de}{'-nv' if nv else ''}"
        try:
            self.query_one("#config_preview", Static).update(text)
        except Exception:
            pass

    def _sim_go(self) -> None:
        files = getattr(self.app, "local_frzr_files", []) or []

        def worker() -> None:
            _wait_page_ack("version")
            if files:

                def show_local() -> None:
                    try:
                        self.query_one("#src_local", RadioButton).value = True
                    except Exception:
                        pass
                    self._apply_source_ui("local")
                    self._refresh_preview()
                    _capture_when_ready(self, "version_local")

                    def after_local() -> None:
                        def w2() -> None:
                            _wait_page_ack("version_local")
                            self.app.call_from_thread(self._sim_maybe_advanced_then_next)

                        threading.Thread(target=w2, daemon=True).start()

                    self.set_timer(0.25, after_local)

                self.app.call_from_thread(show_local)
            else:
                def pick_version() -> None:
                    desk = os.environ.get("INSTALLER_SIM_DESKTOP", "").strip()
                    if desk in ("gnome", "kde"):
                        try:
                            self.query_one(f"#de_{desk}", RadioButton).value = True
                        except Exception:
                            pass
                    nv = os.environ.get("INSTALLER_SIM_NVIDIA", "").strip()
                    if nv in ("1", "true", "yes"):
                        try:
                            self.query_one("#nv_yes", RadioButton).value = True
                        except Exception:
                            pass
                    self._refresh_preview()
                    extra = desk == "kde" or nv in ("1", "true", "yes")
                    if extra:
                        _capture_when_ready(self, "version_kde")

                        def after_kde() -> None:
                            def w2() -> None:
                                _wait_page_ack("version_kde")
                                self.app.call_from_thread(self._sim_maybe_advanced_then_next)

                            threading.Thread(target=w2, daemon=True).start()

                        self.set_timer(0.25, after_kde)
                        return
                    self._sim_maybe_advanced_then_next()

                self.app.call_from_thread(pick_version)

        threading.Thread(target=worker, daemon=True).start()

    def _sim_maybe_advanced_then_next(self) -> None:
        if os.environ.get("INSTALLER_SIM_ADVANCED", "") in ("1", "true", "yes"):
            try:
                self.query_one("#opt_advanced", Checkbox).value = True
            except Exception:
                pass
        self._click_next()

    def _click_next(self) -> None:
        try:
            btn = self.query_one("#next", Button)
            btn.focus()
            self.on_button_pressed(Button.Pressed(btn))
        except Exception:
            if not self._armed:
                self._armed = True
                self.on_next()

    def on_next(self) -> None:
        plan = self.app.plan
        plan.source = self._radio_value("source_set", "online")  # type: ignore[assignment]
        if plan.source == "online" and not WifiService().is_online():
            self._armed = False
            self.app.push_screen(ProductMessageScreen("offline", ""))
            return
        if plan.source == "local":
            files = getattr(self.app, "local_frzr_files", []) or []
            idx = 0
            try:
                idx = int(self._radio_value("local_file_set", "0"))
            except Exception:
                idx = 0
            if not files or idx < 0 or idx >= len(files):
                self._armed = False
                return
            plan.local_file = Path(files[idx]["path"])
            plan.channel = "stable"
            plan.desktop = "gnome"
            plan.nvidia = False
        else:
            plan.local_file = None
            plan.channel = self._radio_value("channel_set", "stable")
            plan.desktop = self._radio_value("desktop_set", "gnome")
            plan.nvidia = self._radio_value("nvidia_set", "no") == "yes"
        try:
            self.app.use_advanced = bool(self.query_one("#opt_advanced", Checkbox).value)
        except Exception:
            self.app.use_advanced = False
        if getattr(self.app, "use_advanced", False):
            self.app.push_screen(AdvancedScreen())
        else:
            self.app.push_screen(InstallScreen())


class AdvancedScreen(WizardScreen):
    shot_name = "advanced"
    step_key = "advanced"
    title_text = flow_copy.ADVANCED_TITLE
    subtitle_text = flow_copy.ADVANCED_SUBTITLE
    nav_spec = (
        ("back", flow_copy.BTN_BACK, ""),
        ("exit", flow_copy.BTN_EXIT, ""),
        ("next", flow_copy.ADVANCED_CONTINUE, "-primary"),
    )
    focus_nav = "next"

    def compose_content(self) -> ComposeResult:
        current = {**default_advanced(), **(self.app.plan.advanced or {})}
        for key, label, desc, default in flow_copy.ADVANCED_OPTIONS:
            yield ProductCheckbox(
                f"{label} — {desc}",
                id=f"adv_{key}",
                value=bool(current.get(key, default)),
            )

    def on_mount(self) -> None:
        super().on_mount()

        def focus_first() -> None:
            try:
                self.query(Checkbox).first().focus()
            except Exception:
                pass

        focus_first()
        self.call_after_refresh(focus_first)

    def on_next(self) -> None:
        adv = default_advanced()
        for key, *_rest in flow_copy.ADVANCED_OPTIONS:
            try:
                adv[key] = bool(self.query_one(f"#adv_{key}", Checkbox).value)
            except Exception:
                pass
        self.app.plan.advanced = adv
        self.app.push_screen(InstallScreen())


class InstallScreen(ExecutionScreen):
    shot_name = "install"
    title_text = "安装系统"
    initial_status = "准备开始安装…"
    service_name = "install"

    def _run(self) -> None:
        plan: InstallPlan = self.app.plan
        status = (
            "正在从本地镜像安装…"
            if plan.source == "local"
            else "正在下载系统镜像…"
        )
        self.app.call_from_thread(
            lambda: self.query_one("#subtitle", Label).update(status)
        )
        apply_advanced_options(plan.advanced)

        def on_event(event: ProgressEvent) -> None:
            if event.kind == EventKind.FINISHED:
                return
            self._emit(event)

        result = DeployService(on_event=on_event).run(plan, log_file=installer_log_file())
        if result.returncode != 0:
            self._emit(
                ProgressEvent.finished(False, error=f"deploy 失败 ({result.returncode})")
            )
        else:
            after_deploy_success()
            self._emit(ProgressEvent.finished(True))

    def on_next(self) -> None:
        self.app.push_screen(CompleteScreen("success"))


class CompleteScreen(WizardScreen):
    shot_name = "complete"
    step_key = "complete"
    focus_nav = "reboot"

    def __init__(self, status: str = "success", summary: str = "", details: str = "") -> None:
        self.status = status
        self.summary = summary
        self.details = details
        if status == "cancelled":
            self.title_text = flow_copy.COMPLETE_CANCEL_TITLE
            self.subtitle_text = summary or flow_copy.COMPLETE_CANCEL_SUMMARY
            self.nav_spec = (
                ("reinstall", flow_copy.BTN_REINSTALL, ""),
                ("exit", flow_copy.BTN_SHELL, ""),
                ("shutdown", flow_copy.BTN_SHUTDOWN, ""),
            )
            self.focus_nav = "reinstall"
        elif status == "failed":
            self.title_text = flow_copy.COMPLETE_FAIL_TITLE
            self.subtitle_text = summary or flow_copy.COMPLETE_FAIL_SUMMARY
            self.nav_spec = (
                ("reinstall", flow_copy.BTN_REINSTALL, ""),
                ("exit", flow_copy.BTN_SHELL, ""),
                ("shutdown", flow_copy.BTN_SHUTDOWN, ""),
            )
            self.focus_nav = "reinstall"
        else:
            self.title_text = flow_copy.COMPLETE_SUCCESS_TITLE
            self.subtitle_text = summary or flow_copy.COMPLETE_SUCCESS_SUMMARY
            self.nav_spec = (
                ("reboot", flow_copy.BTN_REBOOT, "-primary"),
                ("exit", flow_copy.BTN_SHELL, ""),
                ("shutdown", flow_copy.BTN_SHUTDOWN, ""),
            )
            self.focus_nav = "reboot"
        super().__init__()

    def compose(self) -> ComposeResult:
        # Compact card on blue — page mode left a huge empty grey panel.
        with PageFrame():
            yield SystemStatusBar()
            yield from compose_dialog(
                mode="compact",
                title=self.title_text,
                subtitle=self.subtitle_text or None,
                nav_spec=self.nav_spec,
                body=self.compose_content,
            )

    def compose_content(self) -> ComposeResult:
        p = self.app.plan
        target = f"{p.channel}:{p.desktop}{'-nv' if p.nvidia else ''}"
        lines = [
            self.details or "",
            f"磁盘: {p.disk_path()}",
            f"模式: {MODE_CN.get(p.mode, p.mode)}",
            f"来源: {SOURCE_CN.get(p.source, p.source)}",
            f"目标: {target}",
            "",
            flow_copy.LOG_FILE_LINE.format(log_file=installer_log_file()),
            flow_copy.UPLOAD_WORKING,
        ]
        self._body_text = "\n".join(x for x in lines if x)
        yield Static(self._body_text, id="body")

    def on_mount(self) -> None:
        super().on_mount()
        self._start_upload()

    def _start_upload(self) -> None:
        from installer.flow.env import skip_power_actions

        path = installer_log_file()
        if skip_power_actions():
            extra = (
                flow_copy.UPLOAD_SKIPPED
                if os.path.exists(path)
                else flow_copy.UPLOAD_NONE
            )
            self._set_upload_line(extra)
            return
        if not os.path.exists(path):
            self._set_upload_line(flow_copy.UPLOAD_NONE)
            return
        from installer.backend.log_utils import AsyncLogUploader

        def done(url: str | None) -> None:
            extra = (
                f"{flow_copy.UPLOAD_OK}\n{url}"
                if url
                else flow_copy.UPLOAD_FAIL
                + "\n"
                + flow_copy.UPLOAD_HINT.format(log_file=path)
            )
            self.app.call_from_thread(lambda: self._set_upload_line(extra))

        AsyncLogUploader(path, done).start()

    def _set_upload_line(self, extra: str) -> None:
        self._body_text = self._body_text.replace(flow_copy.UPLOAD_WORKING, extra)
        try:
            self.query_one("#body", Static).update(self._body_text)
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "reboot":
            flow_reboot()
            self.app.exit()
            return
        if bid == "shutdown":
            flow_poweroff()
            self.app.exit()
            return
        if bid == "exit":
            self.app.exit()
            return
        if bid == "reinstall":
            self.app.reset_to_welcome()
            return
        super().on_button_pressed(event)

    def on_next(self) -> None:
        if self.status == "success":
            flow_reboot()
        self.app.exit()

    def _sim_go(self) -> None:
        def worker() -> None:
            _wait_page_ack("complete")
            time.sleep(0.8)

            def quit_app() -> None:
                self.app.exit()

            self.app.call_from_thread(quit_app)

        threading.Thread(target=worker, daemon=True).start()


class InstallerTui(App):
    TITLE = f"SkorionOS 安装程序 v{VERSION}"
    # Built-in until skorion-console is registered in __init__.
    theme = "ansi-dark"
    CSS = """
    Screen {
        background: ansi_blue;
        color: ansi_white;
    }
    """
    BINDINGS = [Binding("q", "quit", show=False)]

    def __init__(self, plan: Optional[InstallPlan] = None) -> None:
        # Textual enables Monochrome when NO_COLOR is set — kills brand colors.
        os.environ.pop("NO_COLOR", None)
        # Prefer native 16-color SGR over truecolor (VT cannot show Nord RGB).
        os.environ["TEXTUAL_COLOR_SYSTEM"] = "standard"
        os.environ.pop("COLORTERM", None)
        super().__init__()
        self.register_theme(SKORION_CONSOLE)
        self.theme = "skorion-console"
        self.plan = plan or InstallPlan()
        if not self.plan.advanced:
            self.plan.advanced = default_advanced()
        self.local_frzr_files: List[dict] = list_local_frzr_files()
        self.has_existing_installation = False
        self.use_advanced = False

    def open_complete(self, status: str, summary: str = "", details: str = "") -> None:
        self.push_screen(CompleteScreen(status, summary, details))

    def reset_to_welcome(self) -> None:
        self.plan = InstallPlan()
        self.plan.advanced = default_advanced()
        self.has_existing_installation = False
        self.use_advanced = False
        self.local_frzr_files = list_local_frzr_files()
        while len(self.screen_stack) > 2:
            self.pop_screen()

    def on_mount(self) -> None:
        self.theme = "skorion-console"
        self.push_screen(WelcomeScreen())

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        _trace_focus(event.widget)


def run() -> int:
    os.environ.pop("NO_COLOR", None)
    if "INSTALLER_DRY_RUN" not in os.environ and not os.environ.get(
        "INSTALLER_ALLOW_REAL_FRZR"
    ):
        has_stub = bool(
            os.environ.get("INSTALLER_FRZR_BOOTSTRAP")
            or os.environ.get("INSTALLER_FRZR_DEPLOY")
        )
        if os.environ.get("INSTALLER_DEV") == "1" and not has_stub:
            os.environ.setdefault("INSTALLER_DRY_RUN", "1")
    # fresh shot dedupe each process
    global _SHOT_SEQ, _SHOT_TAKEN
    _SHOT_SEQ = 0
    _SHOT_TAKEN = set()
    app = InstallerTui()
    app.run()
    return 0

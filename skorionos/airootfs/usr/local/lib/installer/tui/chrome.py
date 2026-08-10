"""Shared dialog(1)-faithful chrome for the Textual installer.

Shadow geometry matches dialog util.c / dialog.h:
  SHADOW_COLS = 2, SHADOW_ROWS = 1
  right strip starts at y+1; bottom strip starts at x+2; length = panel width.
Never paint a black plate behind the whole panel.
"""

from __future__ import annotations

from typing import Callable, Iterator, Optional, Sequence, Tuple

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Label, Static

# dialog.h
SHADOW_COLS = 2
SHADOW_ROWS = 1

NavSpec = Sequence[Tuple[str, str, str]]


class DialogButton(Button):
    """dialog(1) buttons — no invented chip colors.

    button_inactive = BLACK on WHITE (same as panel → no visible plate)
    button_active   = WHITE/YELLOW on BLUE
    Runtime paint only exists to beat Textual Button:ansi defaults.
    """

    DEFAULT_CSS = """
    DialogButton {
        margin: 0 1;
        min-width: 14;
        height: 3;
        border: none !important;
        border-top: none !important;
        border-bottom: none !important;
        content-align: center middle;
        text-align: center;
        text-style: bold;
        tint: transparent;
        line-pad: 1;
        background: transparent;
        color: ansi_black;
    }
    """

    def on_mount(self) -> None:
        self._paint(focused=self.has_focus)

    def on_focus(self, event) -> None:  # type: ignore[no-untyped-def]
        self._paint(focused=True)

    def on_blur(self, event) -> None:  # type: ignore[no-untyped-def]
        self._paint(focused=False)

    def watch_disabled(self, disabled: bool) -> None:
        self._paint(focused=self.has_focus)

    def _paint(self, *, focused: bool) -> None:
        self.styles.border = ("none", "transparent")
        self.styles.height = 3
        # Transparent = sit on panel white. No black/cyan/white chip fill.
        self.styles.background = "transparent"
        if self.disabled:
            self.styles.color = "ansi_black"
            self.styles.text_style = "dim"
            return
        if focused:
            # dialog button_active_color / button_label_active_color
            self.styles.background = "ansi_blue"
            self.styles.color = (
                "ansi_bright_yellow"
                if "primary" in self.classes
                else "ansi_bright_white"
            )
            self.styles.text_style = "bold"
        else:
            self.styles.color = "ansi_black"
            self.styles.text_style = "bold"


DIALOG_CSS = """
/* --- Host / titles (screen_color CYAN/BLUE) --- */
DialogHost {
    width: 100%;
    height: 1fr;
    background: ansi_blue;
    padding: 0;
}

DialogHost.compact {
    align: center middle;
}

DialogHost.page {
    padding: 0 2 1 1;
}

#screen_title {
    dock: top;
    width: 100%;
    height: auto;
    background: ansi_blue;
}

#title {
    text-style: bold;
    color: ansi_bright_yellow;
    width: 100%;
    text-align: center;
    height: 1;
    padding: 0 1;
    background: ansi_blue;
}

#subtitle {
    color: ansi_bright_cyan;
    width: 100%;
    text-align: center;
    height: 1;
    padding: 0 1;
    background: ansi_blue;
}

/* --- Dialog box: panel + L-shadow (never black parent under panel) --- */
DialogBox {
    background: ansi_blue;
    padding: 0;
}

DialogBox.compact {
    width: 76;
    height: auto;
    max-width: 100%;
    max-height: 100%;
}

DialogBox.page {
    width: 100%;
    height: 1fr;
}

/* Default auto so compact shrink-wraps. Page overrides to fill. */
#dialog_mid {
    width: 100%;
    height: auto;
}

DialogBox.page #dialog_mid {
    height: 1fr;
}

#dialog_rcol {
    width: 2;
    height: 100%;
    background: ansi_blue;
}

#dialog_r_gap {
    width: 2;
    height: 1;
    min-height: 1;
    max-height: 1;
    background: ansi_blue;
}

#dialog_rshadow {
    width: 2;
    height: 1fr;
    min-height: 1;
    background: ansi_black;
}

#dialog_bot {
    width: 100%;
    height: 1;
    background: ansi_blue;
}

#dialog_b_gap {
    width: 2;
    height: 1;
    background: ansi_blue;
}

#dialog_bshadow {
    width: 1fr;
    height: 1;
    background: ansi_black;
}

/* Panel = dialog_color BLACK/WHITE */
#content {
    width: 1fr;
    height: 100%;
    background: ansi_bright_white;
    color: ansi_black;
    border: solid ansi_bright_white;
    padding: 1 2 1 2;
}

DialogBox.compact #content {
    width: 74;
    height: auto;
    max-width: 100%;
}

#nav {
    dock: bottom;
    width: 100%;
    height: 3;
    margin: 1 0 0 0;
    padding: 0;
    align: center middle;
    background: ansi_bright_white;
}

/* Welcome content inside panel */
#welcome_logo {
    width: 100%;
    height: 1;
    text-align: center;
    color: ansi_blue;
    text-style: bold;
}

#welcome_rule {
    width: 100%;
    color: ansi_black;
    margin: 0 0 1 0;
}

#welcome_device {
    width: 100%;
    text-align: center;
    color: ansi_black;
    margin: 0 0 1 0;
}

#welcome_info {
    width: 100%;
    height: auto;
    color: ansi_black;
    padding: 0 2;
    border: none;
    background: transparent;
    text-align: left;
}

#content.welcome #title {
    background: ansi_bright_white;
    color: ansi_blue;
    text-style: bold;
}

#content.welcome #subtitle {
    background: ansi_bright_white;
    color: ansi_black;
}
"""


class DialogHost(Vertical):
    """Blue screen area that holds screen titles + DialogBox."""


class DialogBox(Vertical):
    """Panel + dialog(1) L-shadow strips."""


def compose_dialog(
    *,
    mode: str,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    nav_spec: Optional[NavSpec] = None,
    body: Optional[Callable[[], Iterator[Widget]]] = None,
    panel_classes: str = "",
) -> ComposeResult:
    """Yield dialog chrome. Caller wraps with PageFrame + status bar."""
    host_cls = "compact" if mode == "compact" else "page"
    with DialogHost(classes=host_cls):
        if title is not None or subtitle is not None:
            with Vertical(id="screen_title"):
                if title is not None:
                    yield Label(title, id="title")
                if subtitle is not None:
                    yield Label(subtitle, id="subtitle")
        with DialogBox(classes=host_cls):
            with Horizontal(id="dialog_mid"):
                if panel_classes:
                    content_ctx = Vertical(id="content", classes=panel_classes)
                else:
                    content_ctx = Vertical(id="content")
                with content_ctx:
                    if body is not None:
                        yield from body()
                    if nav_spec is not None:
                        with Horizontal(id="nav"):
                            for bid, lab, cls in nav_spec:
                                yield DialogButton(lab, id=bid, classes=cls or None)
                with Vertical(id="dialog_rcol"):
                    yield Static("", id="dialog_r_gap")
                    yield Static("", id="dialog_rshadow")
            with Horizontal(id="dialog_bot"):
                yield Static("", id="dialog_b_gap")
                yield Static("", id="dialog_bshadow")

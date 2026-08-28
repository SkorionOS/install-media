"""INSTALLER_SIM_AUTO: walk GTK pages by clicking suggested-action.

Stops on complete so sim never clicks reboot. Live ISO leaves this unset.
"""

from __future__ import annotations

import os
from pathlib import Path

from gi.repository import GLib, Gtk

_PAGE_NAMES = {
    0: "welcome",
    1: "network",
    2: "disk",
    3: "mode",
    4: "partition_adjust",
    5: "confirm",
    6: "bootstrap",
    7: "version",
    8: "advanced",
    9: "install",
    10: "complete",
    11: "message",
}

_state: dict = {"announced": None, "clicked": None}


def attach(app) -> None:
    if os.environ.get("INSTALLER_SIM_AUTO", "") not in ("1", "true", "yes"):
        return
    delay = float(os.environ.get("INSTALLER_SIM_AUTO_DELAY", "0.8"))
    announce(app)
    GLib.timeout_add(int(delay * 1000), lambda: _tick(app))
    GLib.timeout_add(200, lambda: (_maybe_snap(app), True)[1])


def announce(app) -> None:
    marker = os.environ.get("INSTALLER_PAGE_MARKER", "").strip()
    if not marker:
        return
    label = _PAGE_NAMES.get(getattr(app, "current_page", -1), f"page_{app.current_page}")
    try:
        path = Path(marker)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(label + "\n", encoding="utf-8")
        q = path.with_suffix(path.suffix + ".queue")
        with q.open("a", encoding="utf-8") as fh:
            fh.write(label + "\n")
    except Exception:
        pass


def _window_shot() -> bool:
    return os.environ.get("INSTALLER_WINDOW_SHOT", "") in ("1", "true", "yes")


def _ack_matches_label(label: str) -> bool:
    ack = os.environ.get("INSTALLER_PAGE_ACK", "").strip()
    if not ack:
        return True
    try:
        return Path(ack).read_text(encoding="utf-8").strip() == label
    except Exception:
        return False


def _ack_matches(label: str) -> bool:
    if not _window_shot():
        return True
    return _ack_matches_label(label)


def _queue_label(label: str) -> None:
    marker = os.environ.get("INSTALLER_PAGE_MARKER", "").strip()
    if not marker:
        return
    try:
        path = Path(marker)
        path.write_text(label + "\n", encoding="utf-8")
        q = path.with_suffix(path.suffix + ".queue")
        with q.open("a", encoding="utf-8") as fh:
            fh.write(label + "\n")
    except Exception:
        pass


def _label(app) -> str:
    return _PAGE_NAMES.get(getattr(app, "current_page", -1), f"page_{app.current_page}")


def _dump_gtk_png(app: Gtk.Widget, dest: Path) -> bool:
    """In-process GTK4 snapshot — X11 root grabs of gamescope are black."""
    try:
        from gi.repository import Graphene
    except Exception:
        return False
    try:
        native = app.get_native()
        renderer = native.get_renderer() if native is not None else None
        if renderer is None:
            return False
        w = max(int(app.get_width() or 0), 1)
        h = max(int(app.get_height() or 0), 1)
        paintable = Gtk.WidgetPaintable.new(app)
        snapshot = Gtk.Snapshot()
        paintable.snapshot(snapshot, float(w), float(h))
        node = snapshot.to_node()
        if node is None:
            return False
        bounds = Graphene.Rect()
        bounds.init(0.0, 0.0, float(w), float(h))
        texture = renderer.render_texture(node, bounds)
        dest.parent.mkdir(parents=True, exist_ok=True)
        ok = bool(texture.save_to_png(str(dest)))
        return ok and dest.is_file() and dest.stat().st_size > 8_000
    except Exception:
        return False


def _maybe_snap(app: Gtk.Widget) -> None:
    out = os.environ.get("INSTALLER_WINDOW_OUT", "").strip()
    if not out:
        marker = os.environ.get("INSTALLER_PAGE_MARKER", "").strip()
        out = str(Path(marker).parent) if marker else ""
    if not out:
        return
    req = Path(out) / "snap-request"
    if not req.is_file():
        return
    try:
        raw = req.read_text(encoding="utf-8").strip()
        req.unlink()
    except Exception:
        return
    if not raw:
        return
    _dump_gtk_png(app, Path(raw))


def _tick(app) -> bool:
    _maybe_snap(app)
    label = _label(app)
    wait_ack = _state.get("wait_ack")
    if wait_ack and not _ack_matches_label(wait_ack):
        return True
    if wait_ack and _ack_matches_label(wait_ack):
        _state["wait_ack"] = None
        _state["skip_page_ack"] = True
    if _state["announced"] != label:
        announce(app)
        _state["announced"] = label
        _state["clicked"] = None
        _state["skip_page_ack"] = False
        return True
    if not _ack_matches(label) and not _state.get("skip_page_ack"):
        return True
    if getattr(app, "current_page", 0) == 10:
        return False
    if _state["clicked"] == label:
        return True
    if label == "mode":
        _pick_sim_mode(app)
    if label == "partition_adjust":
        _pick_sim_dual(app)
    if label == "version" and not _state.get("version_tuned"):
        extra = _tune_sim_version(app)
        _state["version_tuned"] = True
        if extra:
            _queue_label(extra)
            _state["wait_ack"] = extra
            return True
    if (
        os.environ.get("INSTALLER_SIM_WIFI", "").strip() in ("1", "true", "yes")
        and label == "network"
        and not _state.get("wifi_opened")
    ):
        if _open_sim_wifi_password(app):
            _queue_label("wifi_password")
            _state["wifi_opened"] = True
            _state["wait_ack"] = "wifi_password"
            _state["clicked"] = label
            return True
    if (
        os.environ.get("INSTALLER_SIM_CONFIRM_BACK", "").strip() in ("1", "true", "yes")
        and label == "confirm"
        and not _state.get("confirm_backed")
    ):
        btn = _button_named(app, "返回")
        if btn is not None:
            os.environ["INSTALLER_SIM_CONFIRM_BACK"] = "0"
            _state["confirm_backed"] = True
            _state["clicked"] = label
            btn.emit("clicked")
            return True
    nav = os.environ.get("INSTALLER_SIM_NAV", "").strip()
    at = os.environ.get("INSTALLER_SIM_NAV_AT", "").strip()
    if nav == "exit" and (not at or label == at):
        btn = _button_named(app, "退出")
        if btn is not None:
            _state["clicked"] = label
            btn.emit("clicked")
            return True
    btn = _suggested_action(app)
    if btn is None:
        return True
    _state["clicked"] = label
    btn.emit("clicked")
    return True


_FORWARD_LABELS = ("继续", "开始安装", "开始", "清理")

_MODE_LABELS = {
    "dual": ("双系统安装", "重新安装 (双系统)"),
    "fresh": ("全新安装", "重新安装 (全新)"),
    "repair": ("修复安装",),
}


def _pick_sim_mode(app) -> None:
    forced = os.environ.get("INSTALLER_SIM_MODE", "").strip()
    titles = _MODE_LABELS.get(forced)
    if not titles:
        return

    def widget_text(widget: Gtk.Widget) -> str:
        bits: list[str] = []

        def inner(w: Gtk.Widget) -> None:
            if isinstance(w, Gtk.Label):
                t = w.get_text() or ""
                if t.strip():
                    bits.append(t.strip())
            child = w.get_first_child() if hasattr(w, "get_first_child") else None
            while child is not None:
                inner(child)
                child = child.get_next_sibling()

        inner(widget)
        return " ".join(bits)

    def walk(widget: Gtk.Widget) -> None:
        if isinstance(widget, Gtk.CheckButton):
            blob = (widget.get_label() or "") + " " + widget_text(widget)
            if any(t in blob for t in titles) and not widget.get_active():
                widget.set_active(True)
        child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(app)


def _pick_sim_dual(app) -> None:
    if os.environ.get("INSTALLER_SIM_DUAL", "").strip() != "delete":
        return

    def widget_text(widget: Gtk.Widget) -> str:
        bits: list[str] = []

        def inner(w: Gtk.Widget) -> None:
            if isinstance(w, Gtk.Label):
                t = w.get_text() or ""
                if t.strip():
                    bits.append(t.strip())
            child = w.get_first_child() if hasattr(w, "get_first_child") else None
            while child is not None:
                inner(child)
                child = child.get_next_sibling()

        inner(widget)
        return " ".join(bits)

    def walk(widget: Gtk.Widget) -> None:
        if isinstance(widget, Gtk.CheckButton):
            blob = (widget.get_label() or "") + " " + widget_text(widget)
            if "删除" in blob and not widget.get_active():
                widget.set_active(True)
        child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(app)


def _button_text(btn: Gtk.Button) -> str:
    label = btn.get_label()
    if label:
        return label.strip()
    child = btn.get_child() if hasattr(btn, "get_child") else None
    found: list[str] = []

    def walk(widget: Gtk.Widget) -> None:
        if isinstance(widget, Gtk.Label):
            t = widget.get_text() or ""
            if t.strip():
                found.append(t.strip())
        nxt = widget.get_first_child() if hasattr(widget, "get_first_child") else None
        while nxt is not None:
            walk(nxt)
            nxt = nxt.get_next_sibling()

    if child is not None:
        walk(child)
    return found[-1] if found else ""


def _suggested_action(app) -> Gtk.Button | None:
    found: list[Gtk.Button] = []
    labeled: list[Gtk.Button] = []

    def walk(widget: Gtk.Widget) -> None:
        if isinstance(widget, Gtk.Button) and widget.get_visible() and widget.get_sensitive():
            if widget.has_css_class("suggested-action"):
                found.append(widget)
            elif _button_text(widget) in _FORWARD_LABELS:
                labeled.append(widget)
        child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(app)
    if found:
        return found[-1]
    return labeled[-1] if labeled else None


def _button_named(app: Gtk.Widget, text: str) -> Gtk.Button | None:
    found: list[Gtk.Button] = []

    def walk(widget: Gtk.Widget) -> None:
        if isinstance(widget, Gtk.Button) and widget.get_visible() and widget.get_sensitive():
            if _button_text(widget) == text:
                found.append(widget)
        child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(app)
    return found[-1] if found else None


def _widget_blob(widget: Gtk.Widget) -> str:
    bits: list[str] = []

    def inner(w: Gtk.Widget) -> None:
        if isinstance(w, Gtk.CheckButton):
            t = w.get_label() or ""
            if t.strip():
                bits.append(t.strip())
        if isinstance(w, Gtk.Label):
            t = w.get_text() or ""
            if t.strip():
                bits.append(t.strip())
        child = w.get_first_child() if hasattr(w, "get_first_child") else None
        while child is not None:
            inner(child)
            child = child.get_next_sibling()

    inner(widget)
    return " ".join(bits)


def _activate_matching(app: Gtk.Widget, needles: tuple[str, ...]) -> bool:
    found = False

    def walk(widget: Gtk.Widget) -> None:
        nonlocal found
        if isinstance(widget, Gtk.CheckButton):
            blob = (widget.get_label() or "") + " " + _widget_blob(widget)
            if any(n in blob for n in needles) and not widget.get_active():
                widget.set_active(True)
                found = True
        child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(app)
    return found


def _tune_sim_version(app) -> str | None:
    extra = None
    files = getattr(app, "local_frzr_files", None) or []
    want_local = os.environ.get("INSTALLER_SIM_SOURCE", "").strip() == "local" or (
        files
        and os.environ.get("INSTALLER_SIM_LOCAL", "").strip() in ("1", "true", "yes")
        and os.environ.get("INSTALLER_SIM_DESKTOP", "").strip() != "kde"
        and os.environ.get("INSTALLER_SIM_ONLINE", "1").strip() in ("1", "true", "yes")
    )
    if want_local and files:
        _activate_matching(app, ("本地安装",))
        extra = "version_local"
    desk = os.environ.get("INSTALLER_SIM_DESKTOP", "").strip()
    if desk == "kde":
        _activate_matching(app, ("KDE Plasma",))
        extra = extra or "version_kde"
    if os.environ.get("INSTALLER_SIM_NVIDIA", "").strip() in ("1", "true", "yes"):
        _activate_matching(app, ("NV 版",))
        extra = extra or "version_kde"
    if os.environ.get("INSTALLER_SIM_ADVANCED", "").strip() in ("1", "true", "yes"):
        from installer.flow import copy as flow_copy

        _activate_matching(app, (flow_copy.ADVANCED_ENABLE,))
        app.use_advanced_options = True
    return extra


def _open_sim_wifi_password(app) -> bool:
    wifi_list = getattr(app, "wifi_list", None)
    nm = getattr(app, "nm", None)
    if wifi_list is None or nm is None:
        return False
    i = 0
    while True:
        row = wifi_list.get_row_at_index(i)
        if row is None:
            break
        ap = getattr(row, "ap", None)
        if ap is not None and nm.is_secured(ap):
            wifi_list.select_row(row)
            btn = _button_named(app, "连接")
            if btn is None:
                return False
            btn.emit("clicked")
            return True
        i += 1
    return False


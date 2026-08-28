#!/usr/bin/env python3
"""Drive TUI in a real gnome-terminal window; capture via xdg-desktop-portal.

This is a real compositor screenshot of the terminal window on screen —
NOT Textual export_screenshot / SVG→PNG.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

ROOT = Path(__file__).resolve().parents[1]
# Default: timestamped full-flow dir. Never default-wipe .sim/window-shots (baseline).
_default_out = ROOT / f".sim/full-flow-{time.strftime('%H%M%S')}"
OUT = Path(os.environ.get("INSTALLER_WINDOW_OUT", _default_out))
MARKER = OUT / "page.marker"
QUEUE = OUT / "page.marker.queue"
ACK = OUT / "page.ack"
TITLE = "SKORION-TUI-WINDOW-SHOT"
REF_BASELINE = ROOT / ".sim/window-shots"


def portal_screenshot(dest: Path) -> None:
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    portal = bus.get_object(
        "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop"
    )
    iface = dbus.Interface(portal, "org.freedesktop.portal.Screenshot")
    opts = dbus.Dictionary(
        {
            "interactive": dbus.Boolean(False),
            "modal": dbus.Boolean(False),
        },
        signature="sv",
    )
    handle = iface.Screenshot("", opts)
    box: dict = {}

    def on_response(response, results):
        box["r"] = (int(response), {str(k): str(v) for k, v in results.items()})
        loop.quit()

    req = bus.get_object("org.freedesktop.portal.Desktop", str(handle))
    req.connect_to_signal(
        "Response", on_response, dbus_interface="org.freedesktop.portal.Request"
    )
    loop = GLib.MainLoop()
    GLib.timeout_add_seconds(10, loop.quit)
    loop.run()
    if "r" not in box or box["r"][0] != 0:
        raise RuntimeError(f"portal screenshot failed: {box}")
    uri = box["r"][1].get("uri", "")
    if not uri.startswith("file://"):
        raise RuntimeError(f"bad uri {uri}")
    src = Path(uri[7:])
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
    try:
        src.unlink()
    except Exception:
        pass


def take_screenshot(dest: Path) -> None:
    """Compositor capture. Win5 GNOME 50: portal is click-gated; use screencast."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    backend = os.environ.get("INSTALLER_SHOT_BACKEND", "portal")
    if backend in ("screencast", "gnome"):
        r = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/gnome-wayland-shot.py"),
                str(dest),
                "--hold",
                "0.55",
            ],
            check=False,
        )
        if r.returncode != 0 or not dest.is_file() or dest.stat().st_size < 10_000:
            raise RuntimeError(
                f"screencast shot failed rc={r.returncode} dest={dest}"
            )
        return
    portal_screenshot(dest)


def focus_terminal() -> None:
    # Best-effort: raise gnome-terminal by title (XWayland / xdotool).
    try:
        subprocess.run(
            ["xdotool", "search", "--name", TITLE, "windowactivate"],
            check=False,
            capture_output=True,
        )
        time.sleep(0.15)
    except Exception:
        pass


def main() -> int:
    if OUT.resolve() == REF_BASELINE.resolve():
        print(
            "REFUSE: will not wipe .sim/window-shots baseline; unset INSTALLER_WINDOW_OUT",
            file=sys.stderr,
        )
        return 2
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    MARKER.write_text("", encoding="utf-8")
    QUEUE.write_text("", encoding="utf-8")
    ACK.write_text("", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "skorionos/airootfs/usr/local/lib")
    env["INSTALLER_DEV"] = "1"
    env["INSTALLER_SIMULATION"] = "1"
    env["INSTALLER_SIM_DISK"] = env.get("INSTALLER_SIM_DISK", "nvme0n1")
    env["INSTALLER_SIM_AUTO"] = "1"
    env["INSTALLER_SIM_AUTO_DELAY"] = env.get("INSTALLER_SIM_AUTO_DELAY", "0.35")
    # Seed mock local FRZR images so version page can show 本地安装
    env.setdefault("INSTALLER_SIM_LOCAL", "1")
    env["INSTALLER_WINDOW_SHOT"] = "1"
    env["INSTALLER_PAGE_MARKER"] = str(MARKER)
    env["INSTALLER_PAGE_ACK"] = str(ACK)
    env["INSTALLER_PAGE_ACK_TIMEOUT"] = env.get("INSTALLER_PAGE_ACK_TIMEOUT", "12")
    env["INSTALLER_FRZR_BOOTSTRAP"] = str(
        ROOT / "scripts/installer-stubs/frzr-bootstrap"
    )
    env["INSTALLER_FRZR_DEPLOY"] = str(ROOT / "scripts/installer-stubs/frzr-deploy")
    env["INSTALLER_STUB_SLEEP"] = "0"
    env["INSTALLER_LOG_FILE"] = str(OUT / "tui.log")
    env.pop("INSTALLER_DRY_RUN", None)
    env.pop("INSTALLER_SHOT_DIR", None)  # no SVG path
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    # Textual turns Monochrome when NO_COLOR is set (agent shells often export it).
    env.pop("NO_COLOR", None)
    # Prevent fcitx/ibus candidate bar from covering the TUI (steals keys too).
    env["GTK_IM_MODULE"] = "none"
    env["QT_IM_MODULE"] = "none"
    env["SDL_IM_MODULE"] = ""
    env["XMODIFIERS"] = "@im=none"
    py = os.environ.get("INSTALLER_PYTHON", "python3")

    def esc(v: str) -> str:
        return v.replace("'", "'\\''")

    pass_keys = [
        "PYTHONPATH",
        "INSTALLER_DEV",
        "INSTALLER_SIMULATION",
        "INSTALLER_SIM_DISK",
        "INSTALLER_SIM_AUTO",
        "INSTALLER_SIM_AUTO_DELAY",
        "INSTALLER_SIM_LOCAL",
        "INSTALLER_WINDOW_SHOT",
        "INSTALLER_PAGE_MARKER",
        "INSTALLER_PAGE_ACK",
        "INSTALLER_PAGE_ACK_TIMEOUT",
        "INSTALLER_FRZR_BOOTSTRAP",
        "INSTALLER_FRZR_DEPLOY",
        "INSTALLER_STUB_SLEEP",
        "INSTALLER_LOG_FILE",
        "TERM",
        "COLORTERM",
        "GTK_IM_MODULE",
        "QT_IM_MODULE",
        "SDL_IM_MODULE",
        "XMODIFIERS",
    ]
    for k, v in os.environ.items():
        if (
            k.startswith("INSTALLER_")
            and k not in pass_keys
            and k not in ("INSTALLER_DRY_RUN", "INSTALLER_ALLOW_REAL_FRZR", "INSTALLER_SHOT_DIR")
        ):
            env[k] = v
            pass_keys.append(k)

    run_sh = OUT / "run-tui.sh"
    exports = "\n".join(f"export {k}='{esc(str(env[k]))}'" for k in pass_keys)
    run_sh.write_text(
        "#!/bin/bash\n"
        f"cd '{esc(str(ROOT))}'\n"
        f"{exports}\n"
        "unset INSTALLER_DRY_RUN INSTALLER_SHOT_DIR NO_COLOR\n"
        "exec " + esc(py) + " -m installer.tui_main\n",
        encoding="utf-8",
    )
    run_sh.chmod(0o755)

    # Launch real terminal window (gnome-terminal spawns and returns)
    term = subprocess.Popen(
        [
            "gnome-terminal",
            "--title",
            TITLE,
            "--geometry=120x36",
            "--",
            "bash",
            str(run_sh),
        ],
        start_new_session=True,
    )
    # gnome-terminal returns immediately; find bash/python child later
    time.sleep(1.0)
    focus_terminal()

    seq = 0
    seen: list[str] = []
    queue_pos = 0
    deadline = time.time() + 120
    log = (OUT / "capture.log").open("a", encoding="utf-8")

    try:
        while time.time() < deadline:
            try:
                lines = [
                    ln.strip()
                    for ln in QUEUE.read_text(encoding="utf-8").splitlines()
                    if ln.strip()
                ]
            except Exception:
                lines = []
            if queue_pos < len(lines):
                label = lines[queue_pos]
                queue_pos += 1
                time.sleep(0.3)
                focus_terminal()
                seq += 1
                dest = OUT / f"{seq:02d}_{label}.png"
                try:
                    take_screenshot(dest)
                    size = dest.stat().st_size
                    log.write(f"OK {dest.name} bytes={size}\n")
                    log.flush()
                    if size < 20000:
                        log.write(f"WARN tiny shot {dest.name}\n")
                    seen.append(label)
                    ACK.write_text(label + "\n", encoding="utf-8")
                except Exception as exc:
                    log.write(f"FAIL {label}: {exc}\n")
                    log.flush()
                    ACK.write_text(label + "\n", encoding="utf-8")
                continue
            if "complete" in seen:
                time.sleep(0.4)
                break
            alive = subprocess.run(
                ["pgrep", "-f", "installer.tui_main"],
                capture_output=True,
            )
            if alive.returncode != 0 and seen and time.time() > deadline - 100:
                break
            time.sleep(0.05)
    finally:
        log.close()
        subprocess.run(["pkill", "-f", "installer.tui_main"], check=False)
        try:
            os.killpg(term.pid, signal.SIGTERM)
        except Exception:
            pass

    # Assert
    required = [
        "welcome",
        "network",
        "disk",
        "mode",
        "confirm",
        "bootstrap",  # start OR done acceptable below
        "version",
        "version_local",
        "install",
        "complete",
    ]
    missing = []
    for r in required:
        if r == "bootstrap":
            if "bootstrap" not in seen and "bootstrap_done" not in seen:
                missing.append(r)
        elif r == "install":
            if "install" not in seen and "install_done" not in seen:
                missing.append(r)
        elif r not in seen:
            missing.append(r)
    pngs = sorted(OUT.glob("*.png"))
    tiny = [p.name for p in pngs if p.stat().st_size < 20000]
    result = OUT / "RESULT.txt"
    if missing or tiny or len(pngs) < 8:
        result.write_text(
            f"FAIL\nseen={seen}\nmissing={missing}\ntiny={tiny}\ncount={len(pngs)}\n",
            encoding="utf-8",
        )
        print(result.read_text())
        return 1
    result.write_text(
        f"PASS\nmethod=xdg-desktop-portal+gnome-terminal\nseen={seen}\ncount={len(pngs)}\n",
        encoding="utf-8",
    )
    # Stable pointer so humans don't hunt timestamped folders.
    latest = ROOT / ".sim/shots-latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(OUT.name)
    except Exception:
        pass
    print(result.read_text())
    print(f"shots in {OUT}")
    print(f"alias .sim/shots-latest -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

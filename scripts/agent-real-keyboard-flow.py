#!/usr/bin/env python3
"""Real-user keyboard coverage — no INSTALLER_SIM_AUTO.

Architecture (works on Wayland where xdotool cannot see gnome-terminal):
  1. TUI runs inside a real tmux PTY (120x36).
  2. Every step is driven with `tmux send-keys` Left/Right/Up/Down/Enter —
     the same CSI sequences a physical keyboard produces in a terminal.
  3. gnome-terminal attaches to that session so the UI is on-screen.
  4. Screenshots via xdg-desktop-portal (compositor capture).
  5. Focus id traced to INSTALLER_FOCUS_FILE and asserted after each arrow.

Does not wipe .sim/window-shots/.
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
OUT = Path(
    os.environ.get(
        "INSTALLER_WINDOW_OUT",
        ROOT / f".sim/keyboard-flow-{time.strftime('%H%M%S')}",
    )
)
MARKER = OUT / "page.marker"
QUEUE = OUT / "page.marker.queue"
ACK = OUT / "page.ack"
FOCUS = OUT / "focus.log"
SESSION = os.environ.get("INSTALLER_KBD_TMUX", "skorion-kbd-flow")
TITLE = "SKORION-TUI-KEYBOARD-FLOW"
LOG: Path


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def portal_screenshot(dest: Path) -> None:
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    portal = bus.get_object(
        "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop"
    )
    iface = dbus.Interface(portal, "org.freedesktop.portal.Screenshot")
    opts = dbus.Dictionary(
        {"interactive": dbus.Boolean(False), "modal": dbus.Boolean(False)},
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
            raise RuntimeError(f"screencast shot failed rc={r.returncode}")
        return
    portal_screenshot(dest)


def tmux(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["tmux", "-f", "/dev/null", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def key(*keys: str) -> None:
    """Send real terminal key names (Left/Right/Up/Down/Enter) into the PTY."""
    for k in keys:
        tmux("send-keys", "-t", SESSION, k)
        time.sleep(0.20)


def last_focus() -> str:
    if not FOCUS.is_file():
        return ""
    lines = [ln for ln in FOCUS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return ""
    return lines[-1].split("\t")[-1]


def wait_focus(expected: str, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if last_focus() == expected:
            return
        time.sleep(0.05)
    raise AssertionError(f"focus want={expected!r} got={last_focus()!r}")


def wait_focus_in(allowed: set[str], timeout: float = 5.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        got = last_focus()
        if got in allowed:
            return got
        time.sleep(0.05)
    raise AssertionError(f"focus want one of {allowed} got={last_focus()!r}")


def read_queue() -> list[str]:
    try:
        return [
            ln.strip()
            for ln in QUEUE.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
    except Exception:
        return []


def wait_label(label: str, timeout: float = 40.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if label in read_queue():
            return
        time.sleep(0.05)
    raise TimeoutError(f"timeout waiting page label={label} seen={read_queue()}")


def shot(seq: list[int], name: str) -> Path:
    time.sleep(0.35)
    seq[0] += 1
    dest = OUT / f"{seq[0]:02d}_{name}.png"
    take_screenshot(dest)
    size = dest.stat().st_size
    log(f"SHOT {dest.name} bytes={size}")
    if size < 20000:
        raise RuntimeError(f"tiny screenshot {dest.name}")
    return dest


def ack(label: str) -> None:
    ACK.write_text(label + "\n", encoding="utf-8")
    log(f"ACK {label}")


def capture_and_ack(seq: list[int], label: str, timeout: float = 40.0) -> None:
    wait_label(label, timeout=timeout)
    shot(seq, label)
    ack(label)


def cleanup() -> None:
    tmux("kill-session", "-t", SESSION, check=False)
    subprocess.run(
        ["pkill", "-f", f"title={TITLE}"], check=False, capture_output=True
    )
    # Only kill TUIs that use our focus file / marker (avoid foreign sessions).
    subprocess.run(
        ["pkill", "-f", str(FOCUS)], check=False, capture_output=True
    )


def main() -> int:
    global LOG
    if OUT.resolve() == (ROOT / ".sim/window-shots").resolve():
        print(
            "REFUSE: will not wipe .sim/window-shots; set INSTALLER_WINDOW_OUT",
            file=sys.stderr,
        )
        return 2
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    LOG = OUT / "run.log"
    MARKER.write_text("", encoding="utf-8")
    QUEUE.write_text("", encoding="utf-8")
    ACK.write_text("", encoding="utf-8")
    FOCUS.write_text("", encoding="utf-8")

    cleanup()
    time.sleep(0.2)

    env = {
        "PYTHONPATH": str(ROOT / "skorionos/airootfs/usr/local/lib"),
        "INSTALLER_DEV": "1",
        "INSTALLER_SIMULATION": "1",
        "INSTALLER_SIM_DISK": os.environ.get("INSTALLER_SIM_DISK", "nvme0n1"),
        "INSTALLER_SIM_LOCAL": os.environ.get("INSTALLER_SIM_LOCAL", "1"),
        "INSTALLER_WINDOW_SHOT": "1",
        "INSTALLER_PAGE_MARKER": str(MARKER),
        "INSTALLER_PAGE_ACK": str(ACK),
        "INSTALLER_PAGE_ACK_TIMEOUT": "25",
        "INSTALLER_FOCUS_FILE": str(FOCUS),
        "INSTALLER_FRZR_BOOTSTRAP": str(
            ROOT / "scripts/installer-stubs/frzr-bootstrap"
        ),
        "INSTALLER_FRZR_DEPLOY": str(ROOT / "scripts/installer-stubs/frzr-deploy"),
        "INSTALLER_STUB_SLEEP": "0",
        "INSTALLER_LOG_FILE": str(OUT / "tui.log"),
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "PATH": os.environ.get("PATH", "/usr/bin"),
        "HOME": os.environ.get("HOME", str(Path.home())),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }

    def esc(v: str) -> str:
        return v.replace("'", "'\\''")

    run_sh = OUT / "run-tui.sh"
    exports = "\n".join(f"export {k}='{esc(str(v))}'" for k, v in env.items())
    run_sh.write_text(
        "#!/bin/bash\n"
        f"cd '{esc(str(ROOT))}'\n"
        f"{exports}\n"
        "unset INSTALLER_SIM_AUTO INSTALLER_SIM_AUTO_DELAY "
        "INSTALLER_DRY_RUN INSTALLER_SHOT_DIR\n"
        "exec " + os.environ.get("INSTALLER_PYTHON", "python3") + " -m installer.tui_main\n",
        encoding="utf-8",
    )
    run_sh.chmod(0o755)

    # Detached tmux session = real PTY; keys do not need compositor focus.
    tmux(
        "new-session",
        "-d",
        "-s",
        SESSION,
        "-x",
        "120",
        "-y",
        "36",
        str(run_sh),
    )
    log(f"tmux session={SESSION}")

    # On-screen window for portal evidence (attach to same session).
    term = subprocess.Popen(
        [
            "gnome-terminal",
            "--title",
            TITLE,
            "--geometry=120x36",
            "--",
            "tmux",
            "-f",
            "/dev/null",
            "attach-session",
            "-t",
            SESSION,
        ],
        start_new_session=True,
    )
    log(f"gnome-terminal pid={term.pid} OUT={OUT}")

    # Wait until TUI announced welcome (stronger than pgrep — ignores foreign TUIs).
    try:
        wait_label("welcome", timeout=20)
    except Exception as exc:
        (OUT / "RESULT.txt").write_text(
            f"FAIL\nreason=tui_not_started\nerror={exc}\n", encoding="utf-8"
        )
        print((OUT / "RESULT.txt").read_text())
        cleanup()
        return 1

    time.sleep(0.5)
    seq = [0]
    asserts: list[str] = []

    try:
        # --- welcome ---
        capture_and_ack(seq, "welcome")
        wait_focus("start", 4)
        key("Left")
        wait_focus("exit")
        asserts.append("welcome:Left→exit")
        shot(seq, "welcome_focus_exit")
        key("Right")
        wait_focus("start")
        asserts.append("welcome:Right→start")
        key("Enter")

        # --- network ---
        capture_and_ack(seq, "network")
        wait_focus("next", 4)
        key("Left")
        left1 = wait_focus_in(
            {"disconnect", "connect", "refresh", "back", "reconnect"}
        )
        asserts.append(f"network:Left→{left1}")
        shot(seq, "network_focus_left")
        for _ in range(8):
            if last_focus() == "next":
                break
            key("Right")
        wait_focus("next")
        asserts.append("network:Right→next")
        key("Enter")

        # --- disk (RadioSet focused) ---
        capture_and_ack(seq, "disk")
        # Ensure content focus before proving Left/Right escape into #nav.
        for _ in range(6):
            f = last_focus()
            if f == "disk_set" or f.startswith("disk_"):
                break
            key("BTab")
        deadline = time.time() + 4
        while time.time() < deadline:
            f = last_focus()
            if f == "disk_set" or f.startswith("disk_"):
                break
            time.sleep(0.05)
        else:
            raise AssertionError(f"disk content not focused got={last_focus()!r}")
        key("Right")
        wait_focus("next")
        asserts.append("disk:Right→next")
        key("Left")
        wait_focus("back")
        asserts.append("disk:Left→back")
        shot(seq, "disk_focus_back")
        key("Right")
        wait_focus("next")
        key("Enter")

        # --- mode ---
        capture_and_ack(seq, "mode")
        wait_focus_in({"next", "back", "exit", "mode_set"}, 4)
        key("Right")
        # land on a nav button then ensure next
        for _ in range(4):
            if last_focus() == "next":
                break
            key("Right")
        wait_focus("next")
        key("Enter")

        # --- confirm: prove Left/Right reach 继续(go), then Enter ---
        capture_and_ack(seq, "confirm")
        wait_focus_in({"back", "exit", "go"}, 4)
        # Walk with Right until go (covers start-on-back and start-on-go).
        for _ in range(6):
            if last_focus() == "go":
                break
            key("Right")
        wait_focus("go")
        asserts.append("confirm:Right→go")
        key("Left")
        wait_focus("exit")
        asserts.append("confirm:Left→exit")
        key("Right")
        wait_focus("go")
        wait_label("confirm_go", timeout=5)
        shot(seq, "confirm_go")
        ack("confirm_go")
        key("Enter")

        # --- bootstrap ---
        capture_and_ack(seq, "bootstrap")
        capture_and_ack(seq, "bootstrap_done")
        wait_focus("next", 6)
        key("Enter")

        # --- version → local ---
        capture_and_ack(seq, "version")
        for _ in range(8):
            f = last_focus()
            if f in ("source_set", "src_online", "src_local"):
                break
            key("BTab")
        deadline = time.time() + 4
        while time.time() < deadline:
            if last_focus() in ("source_set", "src_online", "src_local"):
                break
            time.sleep(0.05)
        else:
            raise AssertionError(f"version source not focused got={last_focus()!r}")
        # Move to 本地安装 (second radio). Down from set or from online.
        if last_focus() != "src_local":
            key("Down")
        wait_label("version_local", timeout=10)
        shot(seq, "version_local")
        ack("version_local")
        asserts.append("version:Down→local")
        for _ in range(8):
            if last_focus() == "next":
                break
            key("Right")
        wait_focus("next")
        asserts.append("version:Right→next")
        key("Enter")

        # --- install ---
        capture_and_ack(seq, "install")
        capture_and_ack(seq, "install_done")
        wait_focus("next", 6)
        key("Enter")

        # --- complete ---
        capture_and_ack(seq, "complete")
        wait_focus_in({"reboot", "exit", "shutdown"}, 4)
        key("Left")
        asserts.append(f"complete:Left→{last_focus()}")
        shot(seq, "complete_focus_left")
        for _ in range(4):
            if last_focus() == "exit":
                break
            key("Right")
        if last_focus() == "exit":
            key("Enter")
        time.sleep(0.4)
    except Exception as exc:
        log(f"ERROR {exc}")
        tail = (
            FOCUS.read_text(encoding="utf-8").splitlines()[-12:]
            if FOCUS.is_file()
            else []
        )
        (OUT / "RESULT.txt").write_text(
            f"FAIL\nerror={exc}\nasserts={asserts}\nqueue={read_queue()}\n"
            f"focus_tail={tail}\n",
            encoding="utf-8",
        )
        print((OUT / "RESULT.txt").read_text())
        cleanup()
        try:
            os.killpg(term.pid, signal.SIGTERM)
        except Exception:
            pass
        return 1

    cleanup()
    try:
        os.killpg(term.pid, signal.SIGTERM)
    except Exception:
        pass

    seen = read_queue()
    required = [
        "welcome",
        "network",
        "disk",
        "mode",
        "confirm",
        "confirm_go",
        "bootstrap",
        "bootstrap_done",
        "version",
        "version_local",
        "install",
        "install_done",
        "complete",
    ]
    missing = [r for r in required if r not in seen]
    pngs = sorted(OUT.glob("*.png"))
    tiny = [p.name for p in pngs if p.stat().st_size < 20000]
    need_asserts = [
        "welcome:Left→exit",
        "welcome:Right→start",
        "disk:Right→next",
        "disk:Left→back",
        "confirm:Right→go",
        "confirm:Left→exit",
        "version:Down→local",
        "version:Right→next",
    ]
    miss_a = [a for a in need_asserts if a not in asserts]

    if missing or tiny or miss_a or len(pngs) < 14:
        (OUT / "RESULT.txt").write_text(
            f"FAIL\nmissing={missing}\ntiny={tiny}\nmiss_asserts={miss_a}\n"
            f"asserts={asserts}\ncount={len(pngs)}\n"
            f"method=tmux-send-keys+gnome-terminal+portal+no_SIM_AUTO\n",
            encoding="utf-8",
        )
        print((OUT / "RESULT.txt").read_text())
        return 1

    (OUT / "RESULT.txt").write_text(
        f"PASS\nmethod=tmux-send-keys+gnome-terminal+portal+no_SIM_AUTO\n"
        f"asserts={asserts}\ncount={len(pngs)}\nqueue={seen}\n",
        encoding="utf-8",
    )
    print((OUT / "RESULT.txt").read_text())
    print(f"shots in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

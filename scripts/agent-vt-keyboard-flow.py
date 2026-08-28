#!/usr/bin/env python3
"""Real-key TUI coverage on Linux VT (openvt + /dev/fb0 + uinput).

No INSTALLER_SIM_AUTO. Dual partition_adjust 60/100/200 via Up/Down.
"""

from __future__ import annotations

import fcntl
import importlib.util
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(
    os.environ.get(
        "INSTALLER_VT_OUT",
        ROOT / f".sim/vt-keyboard-{time.strftime('%H%M%S')}",
    )
)
os.environ["INSTALLER_VT_OUT"] = str(OUT)
TTYN = int(os.environ.get("INSTALLER_VT_TTY", "3"))

UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_DEV_SETUP = 0x405C5503
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
EV_SYN, EV_KEY, SYN_REPORT = 0, 1, 0
KEY_ENTER, KEY_TAB = 28, 15
KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT = 103, 108, 105, 106

spec = importlib.util.spec_from_file_location(
    "agent_vt_fb_shots", ROOT / "scripts/agent-vt-fb-shots.py"
)
vt = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(vt)

FOCUS = OUT / "focus.log"
QUEUE = OUT / "page.marker.queue"
ACK = OUT / "page.ack"
MARKER = OUT / "page.marker"


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


def wait_label(label: str, timeout: float = 25.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if label in read_queue():
            return
        time.sleep(0.05)
    raise TimeoutError(f"timeout waiting page label={label} seen={read_queue()}")


def make_uinput(keys: list[int]) -> int:
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_SYN)
    for k in keys:
        fcntl.ioctl(fd, UI_SET_KEYBIT, k)
    name = b"skorion-vt-kbd".ljust(80, b"\0")
    setup = struct.pack("HHHH", 3, 0x2345, 0x6789, 1) + name + struct.pack("I", 0)
    fcntl.ioctl(fd, UI_DEV_SETUP, setup)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    time.sleep(0.4)
    return fd


def emit(fd: int, typ: int, code: int, val: int) -> None:
    os.write(fd, struct.pack("llHHi", 0, 0, typ, code, val))


def tap(fd: int, code: int, delay: float = 0.12) -> None:
    emit(fd, EV_KEY, code, 1)
    emit(fd, EV_SYN, SYN_REPORT, 0)
    time.sleep(delay)
    emit(fd, EV_KEY, code, 0)
    emit(fd, EV_SYN, SYN_REPORT, 0)
    time.sleep(0.18)


def launch_tui() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in (MARKER, QUEUE, ACK, FOCUS):
        p.write_text("", encoding="utf-8")
    rows, cols = vt.native_vt_size()
    vt.reset_vt_geometry(rows, cols)
    print(f"VT tty{TTYN} geometry -> {cols}x{rows} (cols x rows)")
    py = os.environ.get("INSTALLER_PYTHON", "python3")

    def esc(v: str) -> str:
        return v.replace("'", "'\\''")

    env_pass = {
        "PYTHONPATH": str(ROOT / "skorionos/airootfs/usr/local/lib"),
        "TERM": "linux",
        "TEXTUAL_COLOR_SYSTEM": "standard",
        "INSTALLER_DEV": "1",
        "INSTALLER_SIMULATION": "1",
        "INSTALLER_SIM_DISK": os.environ.get("INSTALLER_SIM_DISK", "nvme0n1"),
        "INSTALLER_SIM_LOCAL": os.environ.get("INSTALLER_SIM_LOCAL", "0"),
        "INSTALLER_SIM_MODE": os.environ.get("INSTALLER_SIM_MODE", "dual"),
        "INSTALLER_WINDOW_SHOT": "1",
        "INSTALLER_PAGE_MARKER": str(MARKER),
        "INSTALLER_PAGE_ACK": str(ACK),
        "INSTALLER_PAGE_ACK_TIMEOUT": "25",
        "INSTALLER_FOCUS_FILE": str(FOCUS),
        "INSTALLER_FRZR_BOOTSTRAP": str(ROOT / "scripts/installer-stubs/frzr-bootstrap"),
        "INSTALLER_FRZR_DEPLOY": str(ROOT / "scripts/installer-stubs/frzr-deploy"),
        "INSTALLER_STUB_SLEEP": "0",
        "INSTALLER_LOG_FILE": str(OUT / "tui.log"),
        "INSTALLER_STUB_RECORD": str(OUT / "stub-bootstrap.json"),
        "INSTALLER_STUB_RECORD_DEPLOY": str(OUT / "stub-deploy.json"),
    }
    for k, v in os.environ.items():
        if k.startswith("INSTALLER_SIM_") and k not in env_pass:
            env_pass[k] = v
    exports = "\n".join(f"export {k}='{esc(str(v))}'" for k, v in env_pass.items())
    run_sh = OUT / "run-tui.sh"
    run_sh.write_text(
        "#!/bin/bash\n"
        f"cd '{esc(str(ROOT))}'\n"
        f"{exports}\n"
        "unset INSTALLER_SIM_AUTO INSTALLER_SIM_AUTO_DELAY COLORTERM NO_COLOR "
        "INSTALLER_DRY_RUN INSTALLER_ALLOW_REAL_FRZR\n"
        f"stty rows {rows} cols {cols} 2>/dev/null || true\n"
        f"exec {esc(py)} -m installer.tui_main\n",
        encoding="utf-8",
    )
    run_sh.chmod(0o755)
    vt.sudo("pkill", "-f", "installer.tui_main")
    time.sleep(0.3)
    r = vt.sudo("openvt", "-f", "-c", str(TTYN), "--", "bash", str(run_sh))
    if r.returncode != 0:
        raise RuntimeError(f"openvt failed {r.returncode} {r.stderr!r}")
    time.sleep(1.5)
    vt.sudo("chvt", str(TTYN))
    time.sleep(0.8)


def main() -> int:
    if os.geteuid() != 0:
        print("need root for /dev/uinput (sudo -n python this script)", file=sys.stderr)
        return 2
    cur = (vt.sudo("fgconsole").stdout or b"1").decode().strip() or "1"
    seq = 0
    asserts: list[str] = []
    fd = -1
    try:
        launch_tui()
        fd = make_uinput(
            [KEY_ENTER, KEY_TAB, KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT]
        )

        def cap(label: str) -> None:
            nonlocal seq
            time.sleep(0.35)
            seq += 1
            dest = vt.capture_fb(seq, label)
            if dest is None:
                raise RuntimeError(f"capture failed {label}")
            ACK.write_text(label + "\n", encoding="utf-8")

        wait_label("welcome")
        cap("welcome")
        wait_focus("start", 4)
        tap(fd, KEY_LEFT)
        wait_focus("exit")
        asserts.append("welcome:Left→exit")
        cap("welcome_focus_exit")
        tap(fd, KEY_RIGHT)
        wait_focus("start")
        asserts.append("welcome:Right→start")
        tap(fd, KEY_ENTER)

        wait_label("network")
        cap("network")
        wait_focus("next", 4)
        tap(fd, KEY_LEFT)
        left1 = wait_focus_in({"disconnect", "connect", "refresh", "back", "reconnect"})
        asserts.append(f"network:Left→{left1}")
        cap("network_focus_left")
        for _ in range(8):
            if last_focus() == "next":
                break
            tap(fd, KEY_RIGHT)
        wait_focus("next")
        asserts.append("network:Right→next")
        tap(fd, KEY_ENTER)

        wait_label("disk")
        cap("disk")
        for _ in range(6):
            f = last_focus()
            if f == "disk_set" or f.startswith("disk_"):
                break
            tap(fd, KEY_TAB)
        deadline = time.time() + 4
        while time.time() < deadline:
            f = last_focus()
            if f == "disk_set" or f.startswith("disk_"):
                break
            time.sleep(0.05)
        else:
            raise AssertionError(f"disk content not focused got={last_focus()!r}")
        tap(fd, KEY_RIGHT)
        wait_focus("next")
        asserts.append("disk:Right→next")
        tap(fd, KEY_LEFT)
        wait_focus("back")
        asserts.append("disk:Left→back")
        cap("disk_focus_back")
        tap(fd, KEY_RIGHT)
        wait_focus("next")
        tap(fd, KEY_ENTER)

        wait_label("mode")
        cap("mode")
        wait_focus_in({"next", "back", "exit", "mode_set", "mode_dual", "mode_fresh"}, 4)
        for _ in range(6):
            if last_focus() == "next":
                break
            tap(fd, KEY_RIGHT)
        wait_focus("next")
        tap(fd, KEY_ENTER)

        wait_label("partition_adjust", timeout=15)
        cap("partition_adjust")
        # D-pad through ops then size radios (60 / 100 / 200).
        tap(fd, KEY_DOWN)
        time.sleep(0.2)
        cap("partition_adjust_down1")
        tap(fd, KEY_DOWN)
        time.sleep(0.2)
        cap("partition_adjust_down2")
        tap(fd, KEY_DOWN)
        time.sleep(0.2)
        cap("partition_adjust_size")
        tap(fd, KEY_UP)
        time.sleep(0.2)
        cap("partition_adjust_size_up")
        asserts.append("partition_adjust:Down/Up size radios")
        for _ in range(8):
            if last_focus() == "next":
                break
            tap(fd, KEY_RIGHT)
        wait_focus("next")
        tap(fd, KEY_ENTER)

        wait_label("confirm")
        cap("confirm")
        wait_focus_in({"back", "exit", "go"}, 4)
        for _ in range(6):
            if last_focus() == "go":
                break
            tap(fd, KEY_RIGHT)
        wait_focus("go")
        asserts.append("confirm:Right→go")
        tap(fd, KEY_LEFT)
        wait_focus("exit")
        asserts.append("confirm:Left→exit")
        cap("confirm_focus_exit")
        tap(fd, KEY_RIGHT)
        wait_focus("go")
        cap("confirm_go")

        result = OUT / "RESULT.txt"
        result.write_text(
            "PASS\nmethod=vt-fb0+uinput+no_SIM_AUTO\n"
            f"asserts={asserts}\nqueue={read_queue()}\n",
            encoding="utf-8",
        )
        print(result.read_text())
        latest = ROOT / ".sim/vt-shots-latest"
        try:
            if latest.is_symlink() or latest.exists():
                latest.unlink()
            latest.symlink_to(OUT.name)
        except Exception:
            pass
        return 0
    except Exception as exc:
        (OUT / "RESULT.txt").write_text(
            f"FAIL\nerror={exc}\nasserts={asserts}\nfocus={last_focus()}\n"
            f"queue={read_queue()}\n",
            encoding="utf-8",
        )
        print((OUT / "RESULT.txt").read_text())
        return 1
    finally:
        if fd >= 0:
            try:
                fcntl.ioctl(fd, UI_DEV_DESTROY)
                os.close(fd)
            except Exception:
                pass
        vt.sudo("chvt", cur)
        time.sleep(0.3)
        vt.sudo("pkill", "-f", "installer.tui_main")


if __name__ == "__main__":
    sys.exit(main())

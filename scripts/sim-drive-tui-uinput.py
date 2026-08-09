#!/usr/bin/env python3
"""
Drive REAL installer-tui on a Linux VT with a uinput virtual keyboard.
Assumes INSTALLER_SIMULATION=1 and INSTALLER_SIM_DISK prefers the loop device
(listed first). Flow: Start -> Disk Next -> Mode fresh -> Version -> Confirm Go.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_DEV_SETUP = 0x405C5503
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
EV_SYN, EV_KEY, SYN_REPORT = 0, 1, 0
KEY_ENTER = 28
KEY_TAB = 15
KEY_DOWN = 108
KEY_UP = 103
KEY_ESC = 1
KEY_Q = 16


def make_uinput(keys):
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_SYN)
    for k in keys:
        fcntl.ioctl(fd, UI_SET_KEYBIT, k)
    name = b"installer-sim-kbd".ljust(80, b"\0")
    setup = struct.pack("HHHH", 3, 0x2345, 0x6789, 1) + name + struct.pack("I", 0)
    fcntl.ioctl(fd, UI_DEV_SETUP, setup)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    time.sleep(0.4)
    return fd


def emit(fd, typ, code, val):
    os.write(fd, struct.pack("llHHi", 0, 0, typ, code, val))


def tap(fd, code, delay=0.08):
    emit(fd, EV_KEY, code, 1)
    emit(fd, EV_SYN, SYN_REPORT, 0)
    time.sleep(delay)
    emit(fd, EV_KEY, code, 0)
    emit(fd, EV_SYN, SYN_REPORT, 0)
    time.sleep(delay)


def dump_screen(ttyn: int) -> str:
    raw = Path(f"/dev/vcsu{ttyn}").read_bytes()
    chars = []
    for i in range(0, len(raw) - 3, 4):
        cp = struct.unpack_from("<I", raw, i)[0]
        chars.append(" " if cp == 0 else chr(cp) if cp < 0x110000 else "?")
    text = "".join(chars)
    width = 240 if len(text) % 240 == 0 else 80
    lines = [text[i : i + width].rstrip() for i in range(0, len(text), width)]
    return "\n".join(lines[:70])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tty", type=int, default=15)
    ap.add_argument("--disk", required=True, help="loop name without /dev/")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "skorionos/airootfs/usr/local/lib")
    env["TERM"] = "linux"
    env["INSTALLER_SIMULATION"] = "1"
    env["INSTALLER_SIM_DISK"] = args.disk
    env.setdefault("INSTALLER_FRZR_BOOTSTRAP", "/usr/bin/frzr-bootstrap")
    env.setdefault("INSTALLER_ALLOW_REAL_FRZR", "1")
    env.setdefault(
        "INSTALLER_FRZR_DEPLOY",
        str(root / "scripts/installer-stubs/frzr-deploy"),
    )

    # Launch TUI on VT
    cmd = [
        "openvt",
        "-f",
        "-c",
        str(args.tty),
        "--",
        "bash",
        "-lc",
        f"cd {root} && python3 -m installer.tui_main; echo TUI_EXIT:$?; sleep 3",
    ]
    proc = subprocess.Popen(cmd, env=env)
    time.sleep(1.5)

    fd = make_uinput([KEY_ENTER, KEY_TAB, KEY_DOWN, KEY_UP, KEY_ESC, KEY_Q])
    cur = subprocess.check_output(["fgconsole"], text=True).strip()
    try:
        subprocess.run(["chvt", str(args.tty)], check=False)
        time.sleep(0.5)

        # Welcome: focus Start, Enter
        tap(fd, KEY_ENTER)
        time.sleep(0.6)
        # Disk: SIM disk preferred first — Enter/Tab to Next
        # ListView focused; Tab to Next button, Enter
        tap(fd, KEY_TAB)
        time.sleep(0.2)
        tap(fd, KEY_TAB)
        time.sleep(0.2)
        tap(fd, KEY_ENTER)  # Next on disk
        time.sleep(0.6)
        # Mode: fresh is index 0 — Tab to Next, Enter
        tap(fd, KEY_TAB)
        time.sleep(0.2)
        tap(fd, KEY_ENTER)
        time.sleep(0.6)
        # Version: Tab Next Enter (stable gnome)
        tap(fd, KEY_TAB)
        time.sleep(0.2)
        tap(fd, KEY_ENTER)
        time.sleep(0.6)
        # Confirm: Tab to 开始安装 (second button), Enter
        tap(fd, KEY_TAB)
        time.sleep(0.2)
        tap(fd, KEY_TAB)
        time.sleep(0.2)
        tap(fd, KEY_ENTER)

        # Wait for real bootstrap (can take minutes)
        print("Waiting for bootstrap via TUI (up to 10 minutes)...")
        deadline = time.time() + 600
        passed = False
        while time.time() < deadline:
            time.sleep(5)
            text = dump_screen(args.tty)
            Path(f"/tmp/installer-sim-screen-{args.tty}.txt").write_text(text, encoding="utf-8")
            if "完成" in text or "FINISHED" in text or "Bootstrap complete" in text or "frzr-bootstrap 完成" in text:
                # weak signals
                pass
            # Check loop labels
            labels = subprocess.check_output(
                ["lsblk", "-n", "-o", "LABEL", f"/dev/{args.disk}"], text=True
            )
            if any(x.lower() in labels.lower() for x in ("frzr", "efi", "boot")):
                print("[PASS] labels appeared on sim disk while TUI running")
                print(labels)
                passed = True
                break
            # TUI process ended?
            if proc.poll() is not None:
                print(f"TUI openvt exited early: {proc.returncode}")
                break
            print("... still waiting, labels:", labels.replace("\n", " "))

        screen = dump_screen(args.tty)
        print("--- final screen excerpt ---")
        for ln in screen.splitlines():
            if ln.strip():
                print(ln[:200])

        # Send quit if button available
        tap(fd, KEY_TAB)
        tap(fd, KEY_ENTER)
        time.sleep(1)
    finally:
        subprocess.run(["chvt", cur], check=False)
        fcntl.ioctl(fd, UI_DEV_DESTROY)
        os.close(fd)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Real VT A/B: classic dialog under tee vs script vs new Textual TUI.
Evidence is /dev/vcsu dumps (kernel VT buffer), not rendered images.
"""

from __future__ import annotations

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
KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_TAB, KEY_Q = 105, 106, 28, 15, 16

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".sim" / "ab-vt"


def make_uinput(keys):
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_SYN)
    for k in keys:
        fcntl.ioctl(fd, UI_SET_KEYBIT, k)
    name = b"ab-vt-ui".ljust(80, b"\0")
    setup = struct.pack("HHHH", 3, 0xAB01, 0xCD02, 1) + name + struct.pack("I", 0)
    fcntl.ioctl(fd, UI_DEV_SETUP, setup)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    time.sleep(0.4)
    return fd


def emit(fd, typ, code, val):
    os.write(fd, struct.pack("llHHi", 0, 0, typ, code, val))


def tap(fd, code, delay=0.02):
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
    return "\n".join(lines[:80])


def flood_count(text: str) -> dict:
    return {
        "caret": text.count("^[["),
        "C": text.count("[[C"),
        "D": text.count("[[D"),
        "A": text.count("[[A"),
        "B": text.count("[[B"),
    }


def kill_vt_junk():
    subprocess.run(["pkill", "-f", "dialog --title"], check=False)
    subprocess.run(["pkill", "-f", "installer.tui_main"], check=False)
    time.sleep(0.3)


def write_dialog_wrappers():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "wrap_tee.sh").write_text(
        """#!/bin/bash
export TERM=linux
bash -c 'dialog --title "警告" --yes-label "继续" --no-label "取消安装" --extra-button --extra-label "帮助" --yesno "警告: SkorionOS 将被安装到以下磁盘:\\n\\nnvme0n1\\n\\n您是否要继续?\\n请按左右方向键。若出现 ^[[C/^[[D 刷屏则复现成功。" 12 70' 2>&1 | tee /tmp/ab-vt-tee.log
""",
        encoding="utf-8",
    )
    (OUT / "wrap_script.sh").write_text(
        """#!/bin/bash
export TERM=linux
script -f -c 'dialog --title "警告" --yes-label "继续" --no-label "取消安装" --extra-button --extra-label "帮助" --yesno "警告: SkorionOS 将被安装到以下磁盘:\\n\\nnvme0n1\\n\\n您是否要继续?\\n请按左右方向键。若出现 ^[[C/^[[D 刷屏则复现成功。" 12 70' /tmp/ab-vt-script.log
""",
        encoding="utf-8",
    )
    os.chmod(OUT / "wrap_tee.sh", 0o755)
    os.chmod(OUT / "wrap_script.sh", 0o755)


def run_dialog_case(label: str, wrapper: Path, ttyn: int, fd: int) -> dict:
    kill_vt_junk()
    subprocess.Popen(
        [
            "openvt",
            "-f",
            "-c",
            str(ttyn),
            "--",
            "bash",
            "-lc",
            f"export TERM=linux; bash {wrapper}",
        ]
    )
    time.sleep(1.3)
    subprocess.run(["chvt", str(ttyn)], check=False)
    time.sleep(0.4)
    for _ in range(40):
        tap(fd, KEY_LEFT)
        tap(fd, KEY_RIGHT)
    time.sleep(0.35)
    text = dump_screen(ttyn)
    (OUT / f"vt_{label}.txt").write_text(text, encoding="utf-8")
    info = {"label": label, "has_ui": ("继续" in text) or ("继继续续" in text), **flood_count(text)}
    tap(fd, KEY_ENTER)
    time.sleep(0.3)
    kill_vt_junk()
    return info


def run_tui_case(ttyn: int, fd: int) -> dict:
    kill_vt_junk()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "skorionos/airootfs/usr/local/lib")
    env["TERM"] = "linux"
    env["INSTALLER_SIMULATION"] = "1"
    env["INSTALLER_SIM_DISK"] = "loop2"
    env["INSTALLER_DRY_RUN"] = "1"
    env["INSTALLER_FRZR_BOOTSTRAP"] = str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    env["INSTALLER_FRZR_DEPLOY"] = str(ROOT / "scripts/installer-stubs/frzr-deploy")
    # do NOT auto-advance — we drive keys ourselves
    env.pop("INSTALLER_SIM_AUTO", None)

    subprocess.Popen(
        [
            "openvt",
            "-f",
            "-c",
            str(ttyn),
            "--",
            "bash",
            "-lc",
            f"cd {ROOT} && python3 -m installer.tui_main; sleep 8",
        ],
        env=env,
    )
    time.sleep(2.0)
    subprocess.run(["chvt", str(ttyn)], check=False)
    time.sleep(0.6)

    # Welcome -> Start
    tap(fd, KEY_ENTER, 0.05)
    time.sleep(0.7)
    before_arrows = dump_screen(ttyn)
    (OUT / "vt_tui_01_disk.txt").write_text(before_arrows, encoding="utf-8")

    # Spam arrows like the classic bug repro — must NOT flood as ^[[C/^[[D
    for _ in range(40):
        tap(fd, KEY_LEFT)
        tap(fd, KEY_RIGHT)
    time.sleep(0.4)
    after_arrows = dump_screen(ttyn)
    (OUT / "vt_tui_02_after_arrows.txt").write_text(after_arrows, encoding="utf-8")

    # Navigate forward to confirm so UI progression is visible on VT
    tap(fd, KEY_TAB, 0.05)
    time.sleep(0.15)
    tap(fd, KEY_TAB, 0.05)
    time.sleep(0.15)
    tap(fd, KEY_ENTER, 0.05)  # disk next
    time.sleep(0.7)
    (OUT / "vt_tui_03_mode.txt").write_text(dump_screen(ttyn), encoding="utf-8")
    tap(fd, KEY_TAB, 0.05)
    time.sleep(0.15)
    tap(fd, KEY_ENTER, 0.05)  # mode next
    time.sleep(0.7)
    (OUT / "vt_tui_04_version.txt").write_text(dump_screen(ttyn), encoding="utf-8")
    tap(fd, KEY_TAB, 0.05)
    time.sleep(0.15)
    tap(fd, KEY_ENTER, 0.05)  # version next
    time.sleep(0.7)
    confirm = dump_screen(ttyn)
    (OUT / "vt_tui_05_confirm.txt").write_text(confirm, encoding="utf-8")

    # Left/right on confirm buttons — capture again
    for _ in range(6):
        tap(fd, KEY_LEFT)
        tap(fd, KEY_RIGHT)
    time.sleep(0.3)
    confirm2 = dump_screen(ttyn)
    (OUT / "vt_tui_06_confirm_after_arrows.txt").write_text(confirm2, encoding="utf-8")

    info = {
        "label": "tui",
        "has_ui": ("SkorionOS" in after_arrows) or ("选择" in after_arrows) or ("确认" in confirm),
        "has_confirm": ("确认安装" in confirm) or ("开始安装" in confirm),
        "pages": {
            "disk": "选择安装磁盘" in before_arrows or "loop" in before_arrows.lower(),
            "mode": "选择安装类型" in Path(OUT / "vt_tui_03_mode.txt").read_text(encoding="utf-8"),
            "confirm": "确认安装" in confirm or "开始安装" in confirm,
        },
        **flood_count(after_arrows),
        "confirm_flood": flood_count(confirm2),
    }
    tap(fd, KEY_Q)
    time.sleep(0.4)
    kill_vt_junk()
    return info


def main() -> int:
    if os.geteuid() != 0:
        print("re-exec with sudo", flush=True)
        os.execvp("sudo", ["sudo", "-E", sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]])

    OUT.mkdir(parents=True, exist_ok=True)
    write_dialog_wrappers()
    kill_vt_junk()

    fd = make_uinput([KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_TAB, KEY_Q])
    cur = subprocess.check_output(["fgconsole"], text=True).strip()
    try:
        tee = run_dialog_case("classic_tee", OUT / "wrap_tee.sh", 12, fd)
        script = run_dialog_case("classic_script", OUT / "wrap_script.sh", 13, fd)
        tui = run_tui_case(14, fd)
    finally:
        subprocess.run(["chvt", cur], check=False)
        fcntl.ioctl(fd, UI_DEV_DESTROY)
        os.close(fd)
        kill_vt_junk()

    lines = []
    lines.append("=== REAL VT A/B (evidence = /dev/vcsu dumps) ===")
    lines.append(f"classic_tee:    {tee}")
    lines.append(f"classic_script: {script}")
    lines.append(f"new_tui:        {tui}")
    lines.append("")
    lines.append("Files (open these — they are kernel VT screen buffers):")
    for p in sorted(OUT.glob("vt_*.txt")):
        lines.append(f"  {p}")

    # Verdicts
    ok_bug = tee["has_ui"] and tee["caret"] >= 40
    ok_fix = script["has_ui"] and script["caret"] <= 8
    ok_tui = tui["has_ui"] and tui["caret"] <= 8 and tui.get("has_confirm")
    lines.append("")
    lines.append(f"classic tee reproduces arrow flood: {'PASS' if ok_bug else 'FAIL'}")
    lines.append(f"classic script no flood:            {'PASS' if ok_fix else 'FAIL'}")
    lines.append(f"new TUI no flood + reached confirm:  {'PASS' if ok_tui else 'FAIL'}")
    lines.append("")
    if ok_bug and ok_fix and ok_tui:
        lines.append(
            "COMPARE: On the same real VT + uinput arrows, tee classic floods; "
            "script classic and new TUI do not. New TUI also advanced Welcome→Disk→Mode→Version→Confirm."
        )
        lines.append(
            "This does NOT claim 'prettier'. It claims: new TUI is not broken by the tee/TTY class of failure on VT, and is operable with real keys."
        )
        verdict = 0
    else:
        lines.append("COMPARE: incomplete — see FAIL lines above.")
        verdict = 1

    report = "\n".join(lines) + "\n"
    (OUT / "RESULT.txt").write_text(report, encoding="utf-8")
    print(report)
    return verdict


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Agent drives TUI; every step saves a real Textual screen export (SVG->PNG)."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "skorionos/airootfs/usr/local/lib"
OUT = ROOT / ".sim" / "ui-steps"
sys.path.insert(0, str(LIB))

os.environ.update(
    {
        "INSTALLER_DEV": "1",
        "INSTALLER_SIMULATION": "1",
        "INSTALLER_SIM_DISK": "nvme0n1",
        "INSTALLER_FRZR_BOOTSTRAP": str(ROOT / "scripts/installer-stubs/frzr-bootstrap"),
        "INSTALLER_FRZR_DEPLOY": str(ROOT / "scripts/installer-stubs/frzr-deploy"),
        "INSTALLER_STUB_SLEEP": "0",
        "INSTALLER_STUB_RECORD": str(OUT / "boot.json"),
        "INSTALLER_STUB_RECORD_DEPLOY": str(OUT / "deploy.json"),
        "INSTALLER_REQUIRE_STUB": "1",
        "INSTALLER_LOG_FILE": str(OUT / "tui.log"),
        "TERM": "xterm-256color",
    }
)
os.environ.pop("INSTALLER_SIM_AUTO", None)
os.environ.pop("INSTALLER_DRY_RUN", None)


def svg_to_png(svg_path: Path, png_path: Path) -> None:
    # Prefer magick (real rasterizer of the exported screen SVG).
    r = subprocess.run(
        ["magick", str(svg_path), str(png_path)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0 or not png_path.is_file():
        r2 = subprocess.run(
            ["convert", str(svg_path), str(png_path)],
            capture_output=True,
            text=True,
        )
        if r2.returncode != 0 or not png_path.is_file():
            raise RuntimeError(
                f"svg->png failed\nmagick: {r.stderr}\nconvert: {r2.stderr}"
            )


async def shot(app, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    svg = OUT / f"{name}.svg"
    png = OUT / f"{name}.png"
    data = app.export_screenshot()
    svg.write_text(data, encoding="utf-8")
    svg_to_png(svg, png)
    if not png.is_file() or png.stat().st_size < 100:
        raise RuntimeError(f"empty screenshot {png}")
    print(f"SHOT {name} bytes={png.stat().st_size}", flush=True)
    return png


async def main() -> int:
    from installer.tui.app import InstallerTui

    if OUT.exists():
        for p in OUT.glob("step_*.png"):
            p.unlink()
        for p in OUT.glob("step_*.svg"):
            p.unlink()
    OUT.mkdir(parents=True, exist_ok=True)

    app = InstallerTui()
    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause(0.2)
        await shot(app, "step_01_disk")

        await pilot.press("enter")
        await pilot.pause(0.25)
        await shot(app, "step_02_mode")

        await pilot.press("enter")
        await pilot.pause(0.25)
        await shot(app, "step_03_source")

        await pilot.press("enter")
        await pilot.pause(0.25)
        await shot(app, "step_04_channel")

        await pilot.press("enter")
        await pilot.pause(0.25)
        await shot(app, "step_05_desktop")

        await pilot.press("enter")
        await pilot.pause(0.25)
        await shot(app, "step_06_nvidia")

        await pilot.press("enter")
        await pilot.pause(0.3)
        await shot(app, "step_07_confirm_default_cancel")

        await pilot.press("right")  # 取消 -> 继续
        await pilot.pause(0.2)
        await shot(app, "step_08_confirm_go")

        await pilot.press("enter")
        await pilot.pause(0.4)
        await shot(app, "step_09_progress")

        for _ in range(60):
            await pilot.pause(0.05)
            if (OUT / "boot.json").exists() and (OUT / "deploy.json").exists():
                break
        await pilot.pause(0.3)
        await shot(app, "step_10_done")

    # Classic dialog screenshot via script+dialog in a PTY, captured with `script` then
    # rendered by dialog into an ANSI file; also try a second Textual-free capture:
    # run dialog under `timeout` with `script` and convert with ansilove if present.
    classic_sh = OUT / "classic.sh"
    classic_sh.write_text(
        """#!/bin/bash
export TERM=xterm-256color
export DIALOGRC=/tmp/dialogrc-steps
cat > "$DIALOGRC" <<'RC'
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
dialog --colors --title "\\Z3警告\\Zn" --defaultno \\
  --yes-label "继续" --no-label "取消安装" --extra-button --extra-label "帮助" \\
  --yesno "警告: SkorionOS 将被安装到以下磁盘:\\n\\n    nvme0n1 - 512G Samsung SSD\\n\\n您是否要继续?\\n(在后续步骤可进行更详细的安装选项设置)\\n\\n安装程序版本: v2.1.5" 12 70
""",
        encoding="utf-8",
    )
    classic_sh.chmod(0o755)

    # Capture classic with tmux + ansilove/magick if available
    subprocess.run(["tmux", "kill-session", "-t", "shot-classic"], check=False)
    subprocess.run(
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            "shot-classic",
            "-x",
            "100",
            "-y",
            "32",
            str(classic_sh),
        ],
        check=False,
    )
    await asyncio.sleep(1.2)
    ansi = OUT / "step_00_classic_confirm.ansi"
    plain = OUT / "step_00_classic_confirm.txt"
    subprocess.run(
        ["tmux", "capture-pane", "-t", "shot-classic", "-p", "-e"],
        check=False,
        stdout=ansi.open("w", encoding="utf-8"),
    )
    subprocess.run(
        ["tmux", "capture-pane", "-t", "shot-classic", "-p"],
        check=False,
        stdout=plain.open("w", encoding="utf-8"),
    )
    # Prefer ansilove for true terminal screenshot of classic dialog
    if subprocess.call(["bash", "-lc", "command -v ansilove"], stdout=subprocess.DEVNULL) == 0:
        subprocess.run(
            ["ansilove", "-o", str(OUT / "step_00_classic_confirm.png"), str(ansi)],
            check=False,
        )
    else:
        # Fallback: render captured text with magick label — marked as tmux capture render
        # Only if ansilove missing; still based on real tmux pane content.
        subprocess.run(
            [
                "magick",
                "-size",
                "1200x700",
                "xc:#003d7a",
                "-font",
                "DejaVu-Sans-Mono",
                "-pointsize",
                "16",
                "-fill",
                "white",
                "-gravity",
                "NorthWest",
                "-annotate",
                "+20+20",
                plain.read_text(encoding="utf-8"),
                str(OUT / "step_00_classic_confirm.png"),
            ],
            check=False,
        )
    subprocess.run(["tmux", "send-keys", "-t", "shot-classic", "Escape"], check=False)
    subprocess.run(["tmux", "kill-session", "-t", "shot-classic"], check=False)

    pngs = sorted(OUT.glob("step_*.png"))
    manifest = OUT / "MANIFEST.txt"
    lines = [".sim/ui-steps screenshots (agent-driven)", f"count={len(pngs)}"]
    for p in pngs:
        lines.append(f"{p.name}\t{p.stat().st_size}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(manifest.read_text(), flush=True)
    if len(pngs) < 10:
        print("FAIL: expected >=10 step pngs", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

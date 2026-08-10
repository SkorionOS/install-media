#!/usr/bin/env python3
"""Capture Textual TUI on a real Linux VT via /dev/fb0 (+ /dev/vcsu text).

Uses INSTALLER_SIM_AUTO + page.marker so every wizard page is shot on VT.
Requires passwordless sudo for openvt/chvt/fb0/vcsu.
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TTYN = int(os.environ.get("INSTALLER_VT_TTY", "3"))
OUT = Path(
    os.environ.get(
        "INSTALLER_VT_OUT",
        ROOT / f".sim/vt-fb-{time.strftime('%H%M%S')}",
    )
)


def sudo(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sudo", "-n", *args], check=False, capture_output=True
    )


def native_vt_size() -> tuple[int, int]:
    """Rows, cols for a clean VT (undo sticky stty 120x36 from older shot runs)."""
    env_cols = os.environ.get("INSTALLER_VT_COLS")
    env_rows = os.environ.get("INSTALLER_VT_ROWS")
    if env_cols and env_rows:
        return int(env_rows), int(env_cols)
    for n in (4, 5, 6, 8, 9, 10):
        if n == TTYN:
            continue
        r = sudo("bash", "-c", f"stty size < /dev/tty{n}")
        out = (r.stdout or b"").decode().strip()
        if r.returncode == 0 and out:
            parts = out.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                rows, cols = int(parts[0]), int(parts[1])
                if cols >= 80 and rows >= 24 and (cols, rows) != (120, 36):
                    return rows, cols
    return 67, 240


def reset_vt_geometry(rows: int, cols: int) -> None:
    """Force target VT to native geometry before launching the TUI."""
    sudo(
        "bash",
        "-c",
        f"stty rows {rows} cols {cols} < /dev/tty{TTYN}",
    )


def dump_vcsu(ttyn: int, dest: Path) -> None:
    raw = subprocess.check_output(["sudo", "-n", "cat", f"/dev/vcsu{ttyn}"])
    chars = []
    for i in range(0, len(raw) - 3, 4):
        cp = struct.unpack_from("<I", raw, i)[0]
        chars.append(" " if cp == 0 else chr(cp) if cp < 0x110000 else "?")
    text = "".join(chars)
    width = next((w for w in (120, 80, 160, 200, 240) if len(text) % w == 0), 80)
    lines = [text[i : i + width].rstrip() for i in range(0, len(text), width)]
    dest.write_text("\n".join(lines[:80]), encoding="utf-8")


def capture_fb(seq: int, label: str) -> Path | None:
    name = f"{seq:02d}_{label}"
    raw_path = OUT / f"{name}_raw.png"
    sudo(
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pixel_format",
        "bgra",
        "-video_size",
        "3840x2160",
        "-i",
        "/dev/fb0",
        "-frames:v",
        "1",
        "-update",
        "1",
        str(raw_path),
    )
    sudo("chmod", "644", str(raw_path))
    if not raw_path.exists() or raw_path.stat().st_size < 1000:
        print(f"FAIL fb raw {name}", file=sys.stderr)
        return None
    im = Image.open(raw_path).convert("RGB")
    a = np.array(im)
    mask = a.sum(axis=2) > 25
    if not mask.any():
        print(f"FAIL fb empty {name}", file=sys.stderr)
        return None
    ys, xs = np.where(mask)
    pad = 48
    box = (
        max(0, int(xs.min()) - pad),
        max(0, int(ys.min()) - pad),
        min(im.width, int(xs.max()) + pad),
        min(im.height, int(ys.max()) + pad),
    )
    crop = im.crop(box)
    dest = OUT / f"{name}.png"
    crop.save(dest)
    crop.resize((crop.width * 2, crop.height * 2), Image.NEAREST).save(
        OUT / f"{name}@2x.png"
    )
    dump_vcsu(TTYN, OUT / f"{name}.vcsu.txt")
    # chroma sanity
    d = np.max(a, 2).astype(int) - np.min(a, 2).astype(int)
    print(f"OK {dest.name} crop={crop.size} chroma_max={d.max()}")
    return dest


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cur = (sudo("fgconsole").stdout or b"1").decode().strip() or "1"
    rows, cols = native_vt_size()
    reset_vt_geometry(rows, cols)
    print(f"VT tty{TTYN} geometry -> {cols}x{rows} (cols x rows)")
    marker = OUT / "page.marker"
    queue = OUT / "page.marker.queue"
    ack = OUT / "page.ack"
    for p in (marker, queue, ack):
        p.write_text("", encoding="utf-8")

    run_sh = OUT / "run-tui.sh"
    run_sh.write_text(
        f"""#!/bin/bash
cd '{ROOT}'
export PYTHONPATH='{ROOT}/skorionos/airootfs/usr/local/lib'
export TERM=linux
unset COLORTERM
export TEXTUAL_COLOR_SYSTEM=standard
unset NO_COLOR
export INSTALLER_DEV=1
export INSTALLER_SIMULATION=1
export INSTALLER_SIM_DISK=nvme0n1
export INSTALLER_SIM_LOCAL=1
export INSTALLER_SIM_AUTO=1
export INSTALLER_SIM_AUTO_DELAY=0.55
export INSTALLER_WINDOW_SHOT=1
export INSTALLER_PAGE_MARKER='{marker}'
export INSTALLER_PAGE_ACK='{ack}'
export INSTALLER_PAGE_ACK_TIMEOUT=12
export INSTALLER_FRZR_BOOTSTRAP='{ROOT}/scripts/installer-stubs/frzr-bootstrap'
export INSTALLER_FRZR_DEPLOY='{ROOT}/scripts/installer-stubs/frzr-deploy'
export INSTALLER_STUB_SLEEP=0
export INSTALLER_LOG_FILE='{OUT}/tui.log'
unset INSTALLER_DRY_RUN
# Full fbcon geometry (never 120x36 — sticky small size leaves black FB margins).
stty rows {rows} cols {cols} 2>/dev/null || true
exec python3 -m installer.tui_main
""",
        encoding="utf-8",
    )
    run_sh.chmod(0o755)

    sudo("pkill", "-f", "installer.tui_main")
    time.sleep(0.3)

    r = sudo("openvt", "-f", "-c", str(TTYN), "--", "bash", str(run_sh))
    if r.returncode != 0:
        print("openvt failed", r.returncode, file=sys.stderr)
        return 1
    time.sleep(1.5)
    sudo("chvt", str(TTYN))
    time.sleep(0.8)

    seen: list[str] = []
    seq = 0
    last_mark = ""
    deadline = time.time() + 90
    try:
        while time.time() < deadline:
            try:
                mark = marker.read_text(encoding="utf-8").strip().splitlines()
                mark = mark[-1] if mark else ""
            except Exception:
                mark = ""
            # Also drain queue if app uses it
            try:
                qlines = [
                    ln.strip()
                    for ln in queue.read_text(encoding="utf-8").splitlines()
                    if ln.strip()
                ]
            except Exception:
                qlines = []
            # Prefer queue growth; else marker change
            label = None
            if len(qlines) > len(seen):
                label = qlines[len(seen)]
            elif mark and mark != last_mark and mark not in ("", last_mark):
                # avoid re-shooting same if queue empty
                if not seen or seen[-1] != mark:
                    label = mark
                    last_mark = mark

            if label:
                time.sleep(0.35)
                seq += 1
                capture_fb(seq, label)
                seen.append(label)
                ack.write_text(label + "\n", encoding="utf-8")
                last_mark = label
                if label == "complete":
                    time.sleep(0.4)
                    break
                continue

            alive = subprocess.run(
                ["pgrep", "-f", "installer.tui_main"], capture_output=True
            )
            if alive.returncode != 0 and seen:
                break
            time.sleep(0.05)
    finally:
        sudo("chvt", cur)
        time.sleep(0.3)
        sudo("pkill", "-f", "installer.tui_main")

    latest = ROOT / ".sim/vt-shots-latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(OUT.name)
    except Exception:
        pass

    required = [
        "welcome",
        "network",
        "disk",
        "mode",
        "confirm",
        "version",
        "complete",
    ]
    missing = [r for r in required if r not in seen]
    pngs = sorted(OUT.glob("0*.png"))
    result = OUT / "RESULT.txt"
    if missing or len(pngs) < 6:
        result.write_text(
            f"FAIL\nseen={seen}\nmissing={missing}\ncount={len(pngs)}\n",
            encoding="utf-8",
        )
        print(result.read_text())
        return 1
    result.write_text(
        f"PASS\nmethod=vt-fb0\nseen={seen}\ncount={len(pngs)}\n",
        encoding="utf-8",
    )
    print(result.read_text())
    print(f"shots in {OUT}")
    print(f"alias .sim/vt-shots-latest -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

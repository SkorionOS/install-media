#!/usr/bin/env python3
"""gamescope DRM child: GTK installer + in-session X11 snapshots.

SSH ffmpeg/x11grab of gamescope's Xwayland hangs or returns an all-black
root pixmap. import/ffmpeg must run in this process tree (same DISPLAY).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path


def _has_pixels(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 8_000:
        return False
    try:
        from PIL import Image

        extrema = Image.open(path).convert("RGB").getextrema()
        return any(hi > 25 for _lo, hi in extrema)
    except Exception:
        return path.stat().st_size > 80_000


def _snap(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.unlink(missing_ok=True)
    dpy = os.environ.get("DISPLAY") or ":0"
    env = os.environ.copy()
    r = subprocess.run(
        ["import", "-display", dpy, "-window", "root", str(dest)],
        check=False,
        capture_output=True,
        timeout=8,
        env=env,
    )
    if r.returncode == 0 and _has_pixels(dest):
        return
    dest.unlink(missing_ok=True)
    size = f"{os.environ.get('SCREEN_WIDTH', '1920')}x{os.environ.get('SCREEN_HEIGHT', '1080')}"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "x11grab",
            "-use_shm",
            "0",
            "-draw_mouse",
            "0",
            "-video_size",
            size,
            "-i",
            dpy,
            "-frames:v",
            "1",
            "-update",
            "1",
            str(dest),
        ],
        check=False,
        capture_output=True,
        timeout=8,
        env=env,
    )


def _watch() -> None:
    out = Path(os.environ.get("INSTALLER_WINDOW_OUT", ""))
    if not out:
        return
    req = out / "snap-request"
    log = out / "snap-watch.log"
    while True:
        try:
            if req.is_file():
                raw = req.read_text(encoding="utf-8").strip()
                try:
                    req.unlink()
                except FileNotFoundError:
                    pass
                if raw:
                    dest = Path(raw)
                    try:
                        _snap(dest)
                        log.write_text(
                            f"ok {dest.name} bytes={dest.stat().st_size if dest.is_file() else 0}\n",
                            encoding="utf-8",
                        )
                    except Exception as exc:
                        log.write_text(f"fail {dest}: {exc}\n", encoding="utf-8")
        except Exception as exc:
            try:
                log.write_text(f"watch: {exc}\n", encoding="utf-8")
            except Exception:
                pass
        time.sleep(0.05)


def main() -> int:
    os.environ.pop("WAYLAND_DISPLAY", None)
    os.environ.pop("ENABLE_GAMESCOPE_WSI", None)
    os.environ["GDK_BACKEND"] = "x11"
    if os.environ.get("SKORION_DRM_DBUS") != "1" and shutil.which("dbus-run-session"):
        os.environ["SKORION_DRM_DBUS"] = "1"
        os.execvpe(
            "dbus-run-session",
            ["dbus-run-session", sys.executable, str(Path(__file__).resolve())],
            os.environ,
        )
    out = Path(os.environ.get("INSTALLER_WINDOW_OUT", "/tmp"))
    out.mkdir(parents=True, exist_ok=True)
    session_log = out / "session.log"
    with session_log.open("w", encoding="utf-8") as fh:
        return subprocess.call(
            [sys.executable, "-m", "installer.main"],
            env=os.environ,
            stdout=fh,
            stderr=subprocess.STDOUT,
        )


if __name__ == "__main__":
    raise SystemExit(main())

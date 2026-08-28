#!/usr/bin/env python3
"""Capture the current GNOME Wayland session to a PNG.

GNOME 50 blocks org.gnome.Shell.Screenshot (AccessDenied) and grim (no
wlr-screencopy). xdg-desktop-portal screenshot waits for a click. This uses
org.gnome.Shell.Screencast with a *persistent* D-Bus connection, then extracts
one frame. Keep the connection alive until StopScreencast or the shell aborts
with "Sender has vanished".
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _session_env() -> None:
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    os.environ.setdefault(
        "DBUS_SESSION_BUS_ADDRESS",
        f"unix:path={os.environ['XDG_RUNTIME_DIR']}/bus",
    )


def capture(dest: Path, hold_s: float = 1.0) -> Path:
    _session_env()
    import dbus  # noqa: WPS433 — only needed on a GNOME session host

    dest = dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    bus = dbus.SessionBus()
    sc = dbus.Interface(
        bus.get_object("org.gnome.Shell.Screencast", "/org/gnome/Shell/Screencast"),
        "org.gnome.Shell.Screencast",
    )

    tmp = Path(tempfile.mkdtemp(prefix="gnome-shot-"))
    template = str(tmp / "shot")  # no file extension (GNOME 50 deprecation)
    try:
        ok, used = sc.Screencast(
            template,
            {"framerate": dbus.UInt32(10), "draw-cursor": False},
        )
        if not ok:
            raise RuntimeError(f"Screencast start failed: {used!r}")
        time.sleep(max(hold_s, 0.4))
        if not sc.StopScreencast():
            raise RuntimeError("Screencast stop failed")
        time.sleep(0.25)

        webm = Path(str(used))
        if not webm.is_file():
            cands = sorted(tmp.glob("shot*"))
            if not cands:
                raise RuntimeError(f"no screencast file (reported {used!r})")
            webm = cands[-1]

        r = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-fflags",
                "+genpts",
                "-i",
                str(webm),
                "-frames:v",
                "1",
                "-update",
                "1",
                str(dest),
            ],
            check=False,
        )
        if r.returncode != 0 or not dest.is_file() or dest.stat().st_size < 10_000:
            raise RuntimeError(f"ffmpeg extract failed rc={r.returncode} dest={dest}")
        return dest
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dest", nargs="?", default="/tmp/gnome-wayland-shot.png")
    p.add_argument("--hold", type=float, default=1.0)
    args = p.parse_args()
    try:
        out = capture(Path(args.dest), hold_s=args.hold)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

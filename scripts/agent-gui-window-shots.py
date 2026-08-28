#!/usr/bin/env python3
"""Drive GTK installer under gamescope (ISO path).

Default nested: GNOME screencast of the gamescope window.
INSTALLER_GAMESCOPE_BACKEND=drm: live-ISO embedded KMS + kmsgrab (no GNOME bar).

Does not click reboot. Does not run real frzr. Not a mutter GTK window.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shot_spec import required_pages, seen_enough

ROOT = Path(__file__).resolve().parents[1]
_default_out = ROOT / f".sim/gui-flow-{time.strftime('%H%M%S')}"
OUT = Path(os.environ.get("INSTALLER_WINDOW_OUT", _default_out))
MARKER = OUT / "page.marker"
QUEUE = OUT / "page.marker.queue"
ACK = OUT / "page.ack"


def _screen_size() -> tuple[str, str]:
    p = Path("/sys/class/graphics/fb0/virtual_size")
    try:
        raw = p.read_text().strip()
        if "," in raw:
            w, h = raw.split(",", 1)
            if w.isdigit() and h.isdigit():
                return w, h
    except Exception:
        pass
    return "1280", "800"


def _drm_mode() -> bool:
    return os.environ.get("INSTALLER_GAMESCOPE_BACKEND", "").strip().lower() == "drm"


def _run_to(cmd: list[str], timeout: int = 20, text: bool = False) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            timeout=timeout,
            text=text,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "" if text else b"", "timeout" if text else b"timeout")


def _park_gnome_for_drm() -> None:
    """Free seat0 without systemctl isolate (isolate wedges logind/SSH)."""
    _run_to(["sudo", "-n", "systemctl", "mask", "--runtime", "sddm.service"])
    _run_to(["sudo", "-n", "systemctl", "stop", "sddm.service"])
    time.sleep(0.8)
    listed = _run_to(["loginctl", "list-sessions", "--no-legend"], timeout=10, text=True)
    for line in (listed.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[3] == "seat0":
            _run_to(
                ["sudo", "-n", "loginctl", "terminate-session", parts[0]],
                timeout=15,
            )
    subprocess.run(["pkill", "-x", "gnome-shell"], check=False)
    subprocess.run(["pkill", "-x", "gnome-session"], check=False)
    subprocess.run(["pkill", "-x", "mutter"], check=False)
    for _ in range(20):
        gnome = subprocess.run(["pgrep", "-x", "gnome-shell"], capture_output=True)
        sddm = _run_to(["systemctl", "is-active", "sddm.service"], timeout=10, text=True)
        if gnome.returncode != 0 and sddm.stdout.strip() != "active":
            time.sleep(3.0)
            return
        time.sleep(0.4)
    time.sleep(2.0)


def _unmask_sddm() -> None:
    _run_to(["sudo", "-n", "systemctl", "unmask", "--runtime", "sddm.service"])


def _installer_cmd(py: str) -> list[str]:
    """Product GUI path is gamescope + GTK, not a mutter window.

    Unset parent WAYLAND_DISPLAY so GTK cannot attach to GNOME; GDK_BACKEND=x11
    uses gamescope's Xwayland (same as a live ISO session with no mutter).
    """
    gs = shutil.which("gamescope")
    if not gs:
        raise RuntimeError("gamescope not found")
    w = os.environ.get("INSTALLER_WIDTH") or os.environ.get("SCREEN_WIDTH") or _screen_size()[0]
    h = os.environ.get("INSTALLER_HEIGHT") or os.environ.get("SCREEN_HEIGHT") or _screen_size()[1]
    cmd = [gs]
    if _drm_mode():
        cmd += ["--backend", "drm"]
    cmd += [
        "-f",
        "-F",
        "fsr",
        "--force-grab-cursor",
        "-W",
        str(w),
        "-H",
        str(h),
        "--",
        "env",
        "-u",
        "WAYLAND_DISPLAY",
        "-u",
        "ENABLE_GAMESCOPE_WSI",
        "GDK_BACKEND=x11",
        py,
    ]
    if _drm_mode():
        cmd.append(str(ROOT / "scripts/gui-drm-session.py"))
    else:
        cmd += ["-m", "installer.main"]
    return cmd


def _png_has_pixels(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        sz = path.stat().st_size
    except OSError:
        return False
    if sz < 20_000:
        return False
    return True


def _installer_x11_env() -> dict[str, str] | None:
    """DISPLAY/XAUTHORITY of the GTK child inside gamescope (works when SSH x11grab cannot)."""
    r = subprocess.run(["pgrep", "-n", "-f", "installer.main"], capture_output=True, text=True)
    pid = (r.stdout or "").strip().splitlines()[-1] if r.returncode == 0 else ""
    if not pid.isdigit():
        return None
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return None
    env = {}
    for item in raw.split(b"\0"):
        if b"=" not in item:
            continue
        k, v = item.split(b"=", 1)
        try:
            env[k.decode()] = v.decode()
        except Exception:
            continue
    if not env.get("DISPLAY"):
        return None
    return env


def take_screenshot_kms(dest: Path) -> None:
    """Grab via the gamescope child (same DISPLAY). SSH x11grab hangs or is black."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.unlink(missing_ok=True)
    req = OUT / "snap-request"
    deadline = time.time() + 12
    while time.time() < deadline:
        if _png_has_pixels(dest):
            return
        if dest.is_file() and dest.stat().st_size < 8_000:
            dest.unlink(missing_ok=True)
        if not req.is_file():
            req.write_text(str(dest.resolve()) + "\n", encoding="utf-8")
        time.sleep(0.1)
    raise RuntimeError(f"in-session GTK snap timeout dest={dest.name}")


def take_screenshot(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if _drm_mode():
        take_screenshot_kms(dest)
        return
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
        raise RuntimeError(f"screencast shot failed rc={r.returncode} dest={dest}")


def main() -> int:
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
    env["INSTALLER_SIM_AUTO_DELAY"] = env.get("INSTALLER_SIM_AUTO_DELAY", "0.8")
    env.setdefault("INSTALLER_SIM_LOCAL", "1")
    env["INSTALLER_WINDOW_SHOT"] = "1"
    env["INSTALLER_PAGE_MARKER"] = str(MARKER)
    env["INSTALLER_PAGE_ACK"] = str(ACK)
    env["INSTALLER_PAGE_ACK_TIMEOUT"] = env.get("INSTALLER_PAGE_ACK_TIMEOUT", "12")
    env["INSTALLER_FRZR_BOOTSTRAP"] = str(ROOT / "scripts/installer-stubs/frzr-bootstrap")
    env["INSTALLER_FRZR_DEPLOY"] = str(ROOT / "scripts/installer-stubs/frzr-deploy")
    env["INSTALLER_STUB_SLEEP"] = "0"
    env["INSTALLER_LOG_FILE"] = str(OUT / "gui.log")
    env.pop("INSTALLER_DRY_RUN", None)
    env.pop("INSTALLER_ALLOW_REAL_FRZR", None)
    env.pop("NO_COLOR", None)
    # installer-modular session env (do not wipe /tmp/.X11-unix — that is ISO-only)
    env.setdefault("INTEL_DEBUG", "norbc")
    env.setdefault("mesa_glthread", "true")
    env.setdefault("vk_xwayland_wait_ready", "false")
    env.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")
    env.setdefault("QT_QPA_PLATFORM", "xcb")
    env.setdefault("ENABLE_GAMESCOPE_WSI", "1")
    env["GTK_USE_PORTAL"] = "0"
    env["GIO_USE_VFS"] = "local"
    env["GVFS_DISABLE_FUSE"] = "1"
    env["GSK_RENDERER"] = "cairo"
    env["GTK_A11Y"] = "none"
    env["NO_AT_BRIDGE"] = "1"
    env["XDG_DESKTOP_PORTAL_DIR"] = "/nonexistent"
    sw, sh = _screen_size()
    env.setdefault("SCREEN_WIDTH", sw)
    env.setdefault("SCREEN_HEIGHT", sh)
    env.setdefault("INSTALLER_WIDTH", env["SCREEN_WIDTH"])
    env.setdefault("INSTALLER_HEIGHT", env["SCREEN_HEIGHT"])
    h = int(env["INSTALLER_HEIGHT"])
    if h >= 1440:
        env.setdefault("GDK_SCALE", str(h // 720))
        env.setdefault("UI_SCALE", "1")
    elif h >= 720:
        env.setdefault("GDK_SCALE", "1")
        env.setdefault("UI_SCALE", f"{h / 720:.2f}")
    py = os.environ.get("INSTALLER_PYTHON", "python3")
    cmd = _installer_cmd(py)
    unit = "skorion-gui-drm"
    proc: subprocess.Popen | None = None

    if _drm_mode():
        _park_gnome_for_drm()
        gs_log = OUT / "gamescope.log"
        gs_log.write_text("", encoding="utf-8")
        env_file = OUT / "drm.env"
        skip = {
            "WAYLAND_DISPLAY",
            "DISPLAY",
            "COLORTERM",
            "NO_COLOR",
            "INSTALLER_DRY_RUN",
            "INSTALLER_ALLOW_REAL_FRZR",
            "ENABLE_GAMESCOPE_WSI",
            "DBUS_SESSION_BUS_ADDRESS",
            "DBUS_STARTER_ADDRESS",
            "DBUS_STARTER_BUS_TYPE",
        }
        lines = []
        for k, v in env.items():
            if k in skip or "\n" in str(v):
                continue
            lines.append(f"{k}={v}")
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _run_to(["sudo", "-n", "systemctl", "reset-failed", f"{unit}.service"])
        _run_to(["sudo", "-n", "systemctl", "stop", f"{unit}.service"])
        time.sleep(0.3)
        ttyn = os.environ.get("INSTALLER_GUI_DRM_TTY", "4")
        gs_cmd = [
            "sudo",
            "-n",
            "systemd-run",
            "--collect",
            "--uid=1000",
            "--gid=1000",
            "--unit",
            unit,
            "-p",
            "PAMName=login",
            "-p",
            f"TTYPath=/dev/tty{ttyn}",
            "-p",
            "StandardInput=tty",
            "-p",
            f"StandardOutput=file:{gs_log}",
            "-p",
            f"StandardError=file:{gs_log}",
            "-p",
            f"WorkingDirectory={ROOT}",
            "-p",
            f"EnvironmentFile={env_file}",
            "-p",
            "Environment=XDG_RUNTIME_DIR=/run/user/1000",
            "-p",
            "UnsetEnvironment=WAYLAND_DISPLAY DISPLAY ENABLE_GAMESCOPE_WSI DBUS_SESSION_BUS_ADDRESS",
            "--",
            *cmd,
        ]
        st = subprocess.CompletedProcess(gs_cmd, 1, "", "")
        for attempt in range(2):
            _run_to(["sudo", "-n", "chvt", ttyn], timeout=10)
            time.sleep(0.4)
            r = _run_to(gs_cmd, timeout=30, text=True)
            if r.returncode != 0:
                _unmask_sddm()
                raise RuntimeError(f"systemd-run drm failed: {r.stderr or r.stdout}")
            time.sleep(2.5)
            st = _run_to(["systemctl", "is-active", f"{unit}.service"], timeout=10, text=True)
            if st.stdout.strip() == "active":
                break
            _run_to(["sudo", "-n", "systemctl", "stop", f"{unit}.service"])
            _run_to(["sudo", "-n", "systemctl", "reset-failed", f"{unit}.service"])
            time.sleep(3.0)
        else:
            log_txt = ""
            try:
                log_txt = gs_log.read_text(encoding="utf-8", errors="replace")[-2000:]
            except Exception:
                pass
            _unmask_sddm()
            raise RuntimeError(
                f"gamescope drm unit not active ({st.stdout.strip()}): {log_txt}"
            )
        time.sleep(1.5)
        gnome = subprocess.run(["pgrep", "-x", "gnome-shell"], capture_output=True)
        graphical = subprocess.run(
            ["systemctl", "is-active", "graphical.target"],
            capture_output=True,
            text=True,
        )
        (OUT / "seat.txt").write_text(
            f"unit={st.stdout.strip()}\n"
            f"gnome-shell={'up' if gnome.returncode == 0 else 'down'}\n"
            f"graphical={graphical.stdout.strip()}\n",
            encoding="utf-8",
        )
    else:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            env=env,
            start_new_session=True,
        )
        time.sleep(1.2)

    seq = 0
    seen: list[str] = []
    queue_pos = 0
    deadline = time.time() + 300
    required, counts = required_pages()
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
                time.sleep(0.35)
                seq += 1
                dest = OUT / f"{seq:02d}_{label}.png"
                try:
                    take_screenshot(dest)
                    log.write(f"OK {dest.name} bytes={dest.stat().st_size}\n")
                    seen.append(label)
                except Exception as exc:
                    log.write(f"FAIL {label}: {exc}\n")
                log.flush()
                ACK.write_text(label + "\n", encoding="utf-8")
                continue
            if seen_enough(seen, required, counts):
                time.sleep(0.5)
                break
            alive = True
            if proc is not None:
                alive = proc.poll() is None
            elif _drm_mode():
                st = subprocess.run(
                    ["systemctl", "is-active", f"{unit}.service"],
                    capture_output=True,
                    text=True,
                )
                alive = st.stdout.strip() == "active"
            if not alive:
                break
            time.sleep(0.05)
    finally:
        log.close()
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                proc.kill()
        elif _drm_mode():
            _run_to(["sudo", "-n", "systemctl", "stop", f"{unit}.service"])
            _unmask_sddm()

    missing = [r for r in required if r not in seen]
    pngs = sorted(OUT.glob("*.png"))
    tiny = [p.name for p in pngs if p.stat().st_size < 8000]
    result = OUT / "RESULT.txt"
    min_n = max(2, min(5, len(required)))
    if missing or tiny or len(pngs) < min_n:
        result.write_text(
            f"FAIL\nseen={seen}\nmissing={missing}\ntiny={tiny}\ncount={len(pngs)}\n",
            encoding="utf-8",
        )
        print(result.read_text())
        return 1
    method = "gamescope-drm+x11-session" if _drm_mode() else "gnome-screencast+gtk"
    result.write_text(
        f"PASS\nmethod={method}\nseen={seen}\ncount={len(pngs)}\n",
        encoding="utf-8",
    )
    print(result.read_text())
    print(f"shots in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

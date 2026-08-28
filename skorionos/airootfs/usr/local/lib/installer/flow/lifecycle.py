"""Post bootstrap / deploy side effects (timezone, local files, post_install)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, List, Optional

from .env import simulation

LogFn = Optional[Callable[[str], None]]


def sim_local_frzr_files() -> List[dict]:
    """Local install candidates for INSTALLER_SIMULATION.

    INSTALLER_SIM_LOCAL=1 seeds mock files under INSTALLER_SIM_LOCAL_DIR.
    INSTALLER_SIM_LOCAL_FILES=/a.tar.xz:/b.tar.xz uses real paths.
    """
    out: List[dict] = []
    raw = os.environ.get("INSTALLER_SIM_LOCAL_FILES", "").strip()
    if raw:
        for i, path in enumerate(p for p in raw.split(":") if p.strip()):
            p = Path(path.strip())
            out.append(
                {
                    "filename": p.name,
                    "device": f"/dev/sim{i + 1}",
                    "size": f"{max(p.stat().st_size, 1) // (1024 * 1024)}M"
                    if p.is_file()
                    else "?",
                    "path": str(p),
                }
            )
        return out
    if os.environ.get("INSTALLER_SIM_LOCAL", "") not in ("1", "true", "yes"):
        return []
    root = Path(os.environ.get("INSTALLER_SIM_LOCAL_DIR", "/tmp/skorion-sim-local"))
    root.mkdir(parents=True, exist_ok=True)
    samples = [
        ("skorionos-stable-gnome-2026.08.10.tar.xz", "2.1G", "/dev/sdb1"),
        ("skorionos-stable-kde-nv-2026.08.01.tar.xz", "2.3G", "/dev/sdb1"),
    ]
    for name, size, dev in samples:
        p = root / name
        if not p.exists():
            p.write_bytes(b"SIM_LOCAL_FRZR\n")
        out.append({"filename": name, "device": dev, "size": size, "path": str(p)})
    return out


def _log(log: LogFn, msg: str) -> None:
    if log:
        log(msg)


def default_advanced() -> dict:
    return {
        "firmware_overrides": False,
        "cdn": False,
        "fallback_url": True,
        "debug": False,
    }


def prepare_live_timezone(holder: Any | None = None) -> str:
    """Detect/apply timezone on the live session. No-op if already set or simulating."""
    existing = os.environ.get("INSTALLER_TIMEZONE", "").strip()
    if existing:
        return existing
    if simulation():
        return "UTC"
    try:
        from ..backend.timezone_utils import apply_timezone_to_live, auto_detect_timezone

        tz = auto_detect_timezone()
        apply_timezone_to_live(tz)
        os.environ["INSTALLER_TIMEZONE"] = tz
        if holder is not None:
            holder.timezone_detected = True
        return tz
    except Exception:
        os.environ.setdefault("INSTALLER_TIMEZONE", "UTC")
        return os.environ.get("INSTALLER_TIMEZONE", "UTC")


def after_bootstrap_success(holder: Any, *, steam: bool = True, log: LogFn = None) -> List[dict]:
    """Scan local images; timezone/NTP/Steam on a real live session only."""
    files: List[dict] = []
    if simulation():
        files = list(getattr(holder, "local_frzr_files", []) or [])
        if not files:
            files = sim_local_frzr_files()
            holder.local_frzr_files = files
        return files

    try:
        prepare_live_timezone(holder)
        subprocess.run(["timedatectl", "set-ntp", "true"], check=False)
    except Exception:
        pass

    try:
        from ..backend.local_file_manager import LocalFileManager

        mgr = LocalFileManager()
        holder.local_file_manager = mgr
        files = mgr.scan_files()
        holder.local_frzr_files = files
        if files:
            _log(log, f"找到 {len(files)} 个本地安装文件")
        else:
            _log(log, "未找到本地安装文件（将使用在线安装）")
    except Exception:
        files = list(getattr(holder, "local_frzr_files", []) or [])

    if steam:
        try:
            from ..backend.install_utils import grab_steam_bootstrap_with_progress
            from ..config import config

            grab_steam_bootstrap_with_progress(config.mount_path, lambda *_a, **_k: None)
        except Exception:
            pass
    return files


def apply_advanced_options(options: dict | None, *, log: LogFn = None) -> None:
    """Write firmware quirks / frzr-sk.conf from shared advanced flags."""
    opts = {**default_advanced(), **(options or {})}
    if simulation():
        _log(log, f"advanced skipped (sim): {opts}")
        return

    from ..config import config

    if opts.get("firmware_overrides"):
        quirks_dir = f"{config.mount_path}/etc/device-quirks"
        try:
            os.makedirs(quirks_dir, exist_ok=True)
            with open(f"{quirks_dir}/device-quirks.conf", "w", encoding="utf-8") as fh:
                fh.write("export USE_FIRMWARE_OVERRIDES=1\n")
                fh.write("export USB_WAKE_ENABLED=1\n")
            with open(f"{quirks_dir}/dsdt_override.log", "w", encoding="utf-8") as fh:
                fh.write("LAST_DSDT=None\n")
                fh.write("LAST_BIOS_DATE=None\n")
                fh.write("LAST_BIOS_RELEASE=None\n")
                fh.write("LAST_BIOS_VENDOR=None\n")
                fh.write("LAST_BIOS_VERSION=None\n")
            _log(log, "固件覆盖配置已创建")
        except Exception as exc:
            _log(log, f"固件覆盖配置失败: {exc}")

    conf = "/etc/frzr-sk.conf"
    if os.path.exists(conf):
        try:
            with open(conf, encoding="utf-8") as fh:
                content = fh.read()
            cdn = "true" if opts.get("cdn") else "false"
            fallback = "true" if opts.get("fallback_url") else "false"
            content = re.sub(
                r"^release_cdn\s*=.*", f"release_cdn = {cdn}", content, flags=re.MULTILINE
            )
            content = re.sub(r"^api_cdn\s*=.*", f"api_cdn = {cdn}", content, flags=re.MULTILINE)
            content = re.sub(
                r"^fallback_url\s*=.*",
                f"fallback_url = {fallback}",
                content,
                flags=re.MULTILINE,
            )
            with open(conf, "w", encoding="utf-8") as fh:
                fh.write(content)
            _log(log, f"CDN={'on' if opts.get('cdn') else 'off'} fallback={'on' if opts.get('fallback_url') else 'off'}")
        except Exception as exc:
            _log(log, f"frzr-sk.conf 更新失败: {exc}")
    elif opts.get("cdn") or not opts.get("fallback_url", True):
        _log(log, "frzr-sk.conf 不存在，跳过 CDN/备用源")


def after_deploy_success(*, log: LogFn = None) -> None:
    if simulation():
        return
    from ..backend.install_utils import copy_network_config, copy_timezone_config, post_install
    from ..config import config

    mount = config.mount_path
    try:
        if copy_network_config(mount):
            _log(log, "网络配置已复制")
    except Exception:
        pass
    try:
        tz = os.environ.get("INSTALLER_TIMEZONE", "UTC")
        if copy_timezone_config(mount, tz):
            _log(log, f"时区已设置为: {tz}")
    except Exception:
        pass
    try:
        if post_install(mount):
            _log(log, "系统优化完成")
    except Exception:
        pass

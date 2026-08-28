"""Shared environment flags for installer product flow."""

from __future__ import annotations

import os


def simulation() -> bool:
    return os.environ.get("INSTALLER_SIMULATION", "") in ("1", "true", "yes")


def skip_power_actions() -> bool:
    """Never reboot/poweroff the host from tests, stubs, or dry-run."""
    if os.environ.get("INSTALLER_DEV") == "1":
        return True
    if simulation():
        return True
    if os.environ.get("INSTALLER_DRY_RUN", "") in ("1", "true", "yes"):
        return True
    return False


def log_file() -> str:
    env = os.environ.get("INSTALLER_LOG_FILE", "").strip()
    if env:
        return env
    from ..config import config

    return config.log_file

"""Host power actions — Live ISO complete page."""

from __future__ import annotations

import os

from .env import skip_power_actions


def reboot() -> str:
    if skip_power_actions():
        print("[flow] reboot skipped (dev/sim/dry-run)", flush=True)
        return "skipped"
    os.system("systemctl reboot")
    return "reboot"


def poweroff() -> str:
    if skip_power_actions():
        print("[flow] poweroff skipped (dev/sim/dry-run)", flush=True)
        return "skipped"
    os.system("systemctl poweroff")
    return "poweroff"

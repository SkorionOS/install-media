"""Disk / mode routing used by both GTK and TUI."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .env import simulation


@dataclass(frozen=True)
class DiskContinue:
    """Next product step after the user confirms a target disk."""

    step: str  # too_small | external | incomplete | mode
    has_existing: bool = False


@dataclass(frozen=True)
class DualContinue:
    """Next step after the user picks dual-boot."""

    step: str  # confirm_auto | partition_adjust
    dual_op: str | None = None


def after_disk_selected(disk: str, *, skip_safety: bool | None = None) -> DiskContinue:
    """Safety checks + existing-frzr detection (GUI disk.py continue)."""
    if skip_safety is None:
        skip_safety = simulation()
    if skip_safety:
        gate = os.environ.get("INSTALLER_SIM_DISK_GATE", "").strip()
        if gate == "too_small":
            return DiskContinue("too_small")
        if gate == "external":
            return DiskContinue("external")
        forced = os.environ.get("INSTALLER_SIM_FRZR", "").strip()
        if forced == "complete":
            return DiskContinue("mode", has_existing=True)
        if forced == "incomplete":
            return DiskContinue("incomplete")
        return DiskContinue("mode", has_existing=False)

    from ..backend.disk_utils import (
        check_existing_frzr_installation,
        is_disk_external,
        is_disk_smaller_than,
    )
    from ..config import config

    if is_disk_smaller_than(disk, config.min_disk_size):
        return DiskContinue("too_small")
    if is_disk_external(disk):
        return DiskContinue("external")
    return after_frzr_check(disk)


def after_frzr_check(disk: str) -> DiskContinue:
    # Same sim contract as after_disk_selected — never lsblk the host.
    if simulation():
        forced = os.environ.get("INSTALLER_SIM_FRZR", "").strip()
        if forced == "complete":
            return DiskContinue("mode", has_existing=True)
        if forced == "incomplete":
            return DiskContinue("incomplete")
        return DiskContinue("mode", has_existing=False)

    from ..backend.disk_utils import check_existing_frzr_installation

    status = check_existing_frzr_installation(disk)
    if status == "complete":
        return DiskContinue("mode", has_existing=True)
    if status == "incomplete":
        return DiskContinue("incomplete")
    return DiskContinue("mode", has_existing=False)


def after_dual_selected(disk: str) -> DualContinue:
    """GUI: enough free space → auto dual confirm; else partition adjust."""
    if simulation():
        forced = os.environ.get("INSTALLER_SIM_DUAL", "").strip()
        if forced == "auto":
            return DualContinue("confirm_auto", dual_op="auto")
        # Default partition-adjust so D-pad tests have a stable page.
        return DualContinue("partition_adjust")
    from ..backend.disk_utils import check_free_space

    if check_free_space(disk):
        return DualContinue("confirm_auto", dual_op="auto")
    return DualContinue("partition_adjust")


def shrinkable_partitions(disk: str) -> list:
    """Partitions the dual-boot adjust page can shrink or delete."""
    name = disk.removeprefix("/dev/")
    if simulation():
        if os.environ.get("INSTALLER_SIM_DUAL", "").strip() == "no_shrink":
            return []
        part = (
            f"/dev/{name}p3"
            if ("nvme" in name or "mmcblk" in name)
            else f"/dev/{name}3"
        )
        return [{"path": part, "fstype": "ntfs", "size_gb": 200}]
    from ..backend.disk_utils import list_shrinkable_partitions

    return list_shrinkable_partitions(name) or []

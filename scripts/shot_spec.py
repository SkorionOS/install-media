"""Shared INSTALLER_SIM_* → required page labels for VT/GUI shot runners."""

from __future__ import annotations

import os


def _flag(*names: str) -> bool:
    for name in names:
        if os.environ.get(name, "").strip() in ("1", "true", "yes"):
            return True
    return False


def required_pages() -> tuple[list[str], dict[str, int]]:
    """Return (required labels, min-count per label). Last matching branch wins."""
    frzr = os.environ.get("INSTALLER_SIM_FRZR", "").strip()
    gate = os.environ.get("INSTALLER_SIM_DISK_GATE", "").strip()
    dual = os.environ.get("INSTALLER_SIM_DUAL", "").strip()
    counts: dict[str, int] = {}

    if _flag("INSTALLER_SIM_WIFI"):
        return ["welcome", "network", "wifi_password"], counts
    if gate == "external" and frzr == "incomplete":
        return ["welcome", "network", "disk", "message"], {"message": 2}
    if gate in ("too_small", "external"):
        return ["welcome", "network", "disk", "message"], counts
    if frzr == "incomplete":
        return ["welcome", "network", "disk", "message"], counts
    if dual == "auto":
        return ["welcome", "network", "disk", "mode", "confirm"], counts
    if dual == "delete":
        return [
            "welcome",
            "network",
            "disk",
            "mode",
            "partition_adjust",
            "confirm",
        ], counts
    if dual == "no_shrink":
        return [
            "welcome",
            "network",
            "disk",
            "mode",
            "partition_adjust",
            "message",
        ], counts
    if (
        os.environ.get("INSTALLER_SIM_NAV", "").strip() == "exit"
        and os.environ.get("INSTALLER_SIM_NAV_AT", "").strip() == "mode"
    ):
        return ["welcome", "network", "disk", "mode", "complete"], counts
    if os.environ.get("INSTALLER_STUB_EXIT", "").strip() == "1":
        return ["welcome", "network", "disk", "mode", "confirm", "complete"], counts
    if _flag("INSTALLER_SIM_ADVANCED"):
        return [
            "welcome",
            "network",
            "disk",
            "mode",
            "confirm",
            "version",
            "advanced",
            "complete",
        ], counts
    if os.environ.get("INSTALLER_SIM_ONLINE", "").strip() == "0":
        return [
            "welcome",
            "network",
            "disk",
            "mode",
            "confirm",
            "version",
            "message",
        ], counts
    if os.environ.get("INSTALLER_STUB_DEPLOY_EXIT", "").strip() == "1":
        return [
            "welcome",
            "network",
            "disk",
            "mode",
            "confirm",
            "version",
            "install",
            "complete",
        ], counts
    if _flag("INSTALLER_SIM_CONFIRM_BACK"):
        return ["welcome", "network", "disk", "mode", "confirm"], {"confirm": 2}
    if os.environ.get("INSTALLER_SIM_DESKTOP", "").strip() == "kde":
        return [
            "welcome",
            "network",
            "disk",
            "mode",
            "confirm",
            "version",
            "version_kde",
            "install",
        ], counts
    if os.environ.get("INSTALLER_SIM_LOCAL", "1").strip() in ("1", "true", "yes") and os.environ.get(
        "INSTALLER_SIM_SOURCE", ""
    ).strip() == "local":
        return [
            "welcome",
            "network",
            "disk",
            "mode",
            "confirm",
            "version",
            "version_local",
            "install",
        ], counts
    return ["welcome", "network", "disk", "mode", "confirm", "version", "complete"], counts


def seen_enough(seen: list[str], required: list[str], counts: dict[str, int]) -> bool:
    if any(label not in seen for label in required):
        return False
    for label, need in counts.items():
        if seen.count(label) < need:
            return False
    return True

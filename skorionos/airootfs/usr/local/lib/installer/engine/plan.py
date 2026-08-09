"""InstallPlan: single source of truth for an install session."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

InstallMode = Literal["repair", "fresh", "dual"]
DualOp = Literal["auto", "shrink", "delete"]
InstallSource = Literal["online", "local"]


@dataclass
class InstallPlan:
    """User intent + parameters consumed by InstallEngine / frzr."""

    disk: str = ""
    mode: InstallMode = "fresh"
    dual_op: Optional[DualOp] = None
    shrink_partition: Optional[str] = None
    shrink_size_gb: Optional[int] = None
    delete_partition: Optional[str] = None

    source: InstallSource = "online"
    channel: str = "stable"
    desktop: str = "gnome"
    nvidia: bool = False
    local_file: Optional[Path] = None

    advanced: dict[str, Any] = field(default_factory=dict)
    timezone: Optional[str] = None
    username: str = "gamer"

    def disk_path(self) -> str:
        if not self.disk:
            return ""
        return self.disk if self.disk.startswith("/dev/") else f"/dev/{self.disk}"

    def disk_name(self) -> str:
        return self.disk[5:] if self.disk.startswith("/dev/") else self.disk

    def validate_for_bootstrap(self) -> list[str]:
        """Return a list of validation errors (empty means OK)."""
        errors: list[str] = []
        if not self.disk:
            errors.append("disk is required")
        if self.mode not in ("repair", "fresh", "dual"):
            errors.append(f"invalid mode: {self.mode!r}")
        if self.mode == "dual":
            op = self.dual_op or "auto"
            if op not in ("auto", "shrink", "delete"):
                errors.append(f"invalid dual_op: {op!r}")
            if op == "shrink":
                if not self.shrink_partition:
                    errors.append("shrink_partition is required for dual shrink")
                if not self.shrink_size_gb or self.shrink_size_gb <= 0:
                    errors.append("shrink_size_gb must be > 0 for dual shrink")
            if op == "delete" and not self.delete_partition:
                errors.append("delete_partition is required for dual delete")
        return errors

    def validate_for_deploy(self) -> list[str]:
        errors: list[str] = []
        if self.source == "local":
            if not self.local_file:
                errors.append("local_file is required for local install")
            elif not Path(self.local_file).is_file():
                errors.append(f"local_file does not exist: {self.local_file}")
        elif self.source != "online":
            errors.append(f"invalid source: {self.source!r}")
        return errors

    @classmethod
    def from_app_state(cls, app) -> "InstallPlan":
        """Build a plan from the current GTK InstallerApp attributes."""
        disk = getattr(app, "selected_disk", "") or ""
        mode = getattr(app, "install_mode", "fresh") or "fresh"
        dual_op = getattr(app, "dual_mode", None)
        shrink_partition = getattr(app, "shrink_partition", None)
        shrink_size = getattr(app, "shrink_size", None)
        delete_partition = getattr(app, "delete_partition", None)

        version = getattr(app, "version_selections", {}) or {}
        source = version.get("install_mode", "online")
        if source not in ("online", "local"):
            source = "online"
        local = version.get("local_file")
        local_path = Path(local) if local else None

        advanced = getattr(app, "advanced_options", None) or {}
        timezone = None
        import os

        timezone = os.environ.get("INSTALLER_TIMEZONE")

        return cls(
            disk=disk,
            mode=mode,
            dual_op=dual_op,
            shrink_partition=shrink_partition,
            shrink_size_gb=int(shrink_size) if shrink_size else None,
            delete_partition=delete_partition,
            source=source,
            channel=version.get("channel", "stable"),
            desktop=version.get("desktop", "gnome"),
            nvidia=bool(version.get("nvidia", False)),
            local_file=local_path,
            advanced=dict(advanced),
            timezone=timezone,
        )

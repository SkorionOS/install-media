"""Bootstrap orchestration: InstallPlan -> frzr-bootstrap argv/env."""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Tuple

from .events import ProgressEvent
from .plan import InstallPlan
from .runner import CommandRunner, RunResult

EventCallback = Callable[[ProgressEvent], None]


def bootstrap_argv(plan: InstallPlan, bootstrap_bin: Optional[str] = None) -> List[str]:
    tool = bootstrap_bin or CommandRunner.resolve_tool(
        "frzr-bootstrap", "INSTALLER_FRZR_BOOTSTRAP"
    )
    return [tool, plan.username, plan.disk_path(), plan.mode]


def bootstrap_env(plan: InstallPlan) -> Dict[str, str]:
    """Return env *overlay* (not full environ) for noninteractive frzr-bootstrap."""
    env = {"FRZR_NONINTERACTIVE": "1"}
    if plan.mode != "dual":
        return env

    op = plan.dual_op or "auto"
    if op == "shrink":
        env["FRZR_SHRINK_PARTITION"] = plan.shrink_partition or ""
        env["FRZR_SHRINK_SIZE"] = str(plan.shrink_size_gb or "")
    elif op == "delete":
        env["FRZR_DELETE_PARTITION"] = plan.delete_partition or ""
    return env


def bootstrap_spec(plan: InstallPlan) -> Tuple[List[str], Dict[str, str]]:
    errors = plan.validate_for_bootstrap()
    if errors:
        raise ValueError("invalid InstallPlan for bootstrap: " + "; ".join(errors))
    return bootstrap_argv(plan), bootstrap_env(plan)


class BootstrapService:
    """Runs frzr-bootstrap from an InstallPlan."""

    def __init__(self, on_event: Optional[EventCallback] = None):
        self.runner = CommandRunner(on_event=on_event)

    @property
    def process(self):
        return self.runner.process

    def cancel(self) -> None:
        self.runner.cancel()

    def run(self, plan: InstallPlan, *, log_file: Optional[str] = None) -> RunResult:
        argv, env = bootstrap_spec(plan)
        # Guard: refuse real frzr unless explicitly allowed when not dry-run
        if (
            not CommandRunner.dry_run_enabled()
            and not CommandRunner.real_frzr_allowed()
            and os.environ.get("INSTALLER_FRZR_BOOTSTRAP") is None
            and self._is_system_frzr(argv[0])
        ):
            # Allow normal ISO/live path: real frzr is expected when not dry-run.
            # Safety gate only when INSTALLER_REQUIRE_STUB=1 (dev/test).
            if os.environ.get("INSTALLER_REQUIRE_STUB", "") in ("1", "true", "yes"):
                raise RuntimeError(
                    "Refusing to run system frzr-bootstrap "
                    "(set INSTALLER_DRY_RUN=1 or INSTALLER_FRZR_BOOTSTRAP=stub)"
                )

        self.runner.emit(ProgressEvent.stage("bootstrap", f"mode={plan.mode} disk={plan.disk_path()}"))
        if log_file:
            os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
            with open(log_file, "w", encoding="utf-8") as fh:
                fh.write("=== frzr-bootstrap started (engine) ===\n")
                fh.write(f"Mode: {plan.mode}\n")
                fh.write(f"Disk: {plan.disk_path()}\n")
                if plan.mode == "dual":
                    fh.write(f"Dual op: {plan.dual_op or 'auto'}\n")
                    if (plan.dual_op or "auto") == "shrink":
                        fh.write(
                            f"Shrink: {plan.shrink_partition} by {plan.shrink_size_gb}GB\n"
                        )
                    elif plan.dual_op == "delete":
                        fh.write(f"Delete: {plan.delete_partition}\n")

        return self.runner.run(argv, env=env, log_file=log_file, stage="bootstrap")

    @staticmethod
    def _is_system_frzr(path: str) -> bool:
        return path in ("frzr-bootstrap", "/usr/bin/frzr-bootstrap")

"""Deploy orchestration: InstallPlan -> frzr-deploy argv/env."""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Tuple

from .events import ProgressEvent
from .plan import InstallPlan
from .runner import CommandRunner, RunResult

EventCallback = Callable[[ProgressEvent], None]


def deploy_target(plan: InstallPlan) -> str:
    if plan.source == "local":
        if not plan.local_file:
            raise ValueError("local_file is required for local deploy")
        return str(plan.local_file)
    suffix = "-nv" if plan.nvidia else ""
    return f"3003n/skorionos:{plan.channel}:{plan.desktop}{suffix}"


def deploy_argv(plan: InstallPlan, deploy_bin: Optional[str] = None) -> List[str]:
    tool = deploy_bin or CommandRunner.resolve_tool("frzr-deploy", "INSTALLER_FRZR_DEPLOY")
    return [tool, deploy_target(plan)]


def deploy_env(plan: InstallPlan) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if plan.advanced.get("debug"):
        env["DEBUG"] = "1"
    return env


def deploy_spec(plan: InstallPlan) -> Tuple[List[str], Dict[str, str]]:
    errors = plan.validate_for_deploy()
    if errors:
        raise ValueError("invalid InstallPlan for deploy: " + "; ".join(errors))
    return deploy_argv(plan), deploy_env(plan)


class DeployService:
    """Runs frzr-deploy from an InstallPlan."""

    def __init__(self, on_event: Optional[EventCallback] = None):
        self.runner = CommandRunner(on_event=on_event)

    @property
    def process(self):
        return self.runner.process

    def cancel(self) -> None:
        self.runner.cancel()

    def run(self, plan: InstallPlan, *, log_file: Optional[str] = None) -> RunResult:
        argv, env = deploy_spec(plan)
        if (
            os.environ.get("INSTALLER_REQUIRE_STUB", "") in ("1", "true", "yes")
            and os.environ.get("INSTALLER_FRZR_DEPLOY") is None
            and argv[0] in ("frzr-deploy", "/usr/bin/frzr-deploy")
            and not CommandRunner.dry_run_enabled()
        ):
            raise RuntimeError(
                "Refusing to run system frzr-deploy "
                "(set INSTALLER_DRY_RUN=1 or INSTALLER_FRZR_DEPLOY=stub)"
            )

        self.runner.emit(
            ProgressEvent.stage("deploy", f"source={plan.source} target={deploy_target(plan)}")
        )
        if log_file:
            os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as fh:
                fh.write(f"\n{'=' * 60}\n")
                fh.write("=== frzr-deploy started (engine) ===\n")
                fh.write(f"{'=' * 60}\n")
                fh.write(f"Install mode: {plan.source}\n")
                if plan.source == "local":
                    fh.write(f"Local file: {plan.local_file}\n\n")
                else:
                    fh.write(f"Channel: {plan.channel}\n")
                    fh.write(f"Desktop: {plan.desktop}\n")
                    fh.write(f"NVIDIA: {plan.nvidia}\n\n")

        return self.runner.run(argv, env=env, log_file=log_file, stage="deploy")

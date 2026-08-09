"""
InstallEngine: UI-agnostic install orchestration.

No Gtk / Textual / dialog imports allowed in this package.
"""

from .plan import InstallPlan, DualOp, InstallMode, InstallSource
from .events import EventKind, ProgressEvent
from .bootstrap import BootstrapService, bootstrap_argv, bootstrap_env, bootstrap_spec
from .deploy import DeployService, deploy_argv, deploy_env, deploy_spec, deploy_target
from .runner import CommandRunner, RunResult

__all__ = [
    "InstallPlan",
    "DualOp",
    "InstallMode",
    "InstallSource",
    "EventKind",
    "ProgressEvent",
    "BootstrapService",
    "bootstrap_argv",
    "bootstrap_env",
    "bootstrap_spec",
    "DeployService",
    "deploy_argv",
    "deploy_env",
    "deploy_spec",
    "deploy_target",
    "CommandRunner",
    "RunResult",
]

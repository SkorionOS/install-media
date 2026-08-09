"""Command runner with dry-run / stub / cancel support."""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .events import ProgressEvent

LogCallback = Callable[[ProgressEvent], None]


@dataclass
class RunResult:
    returncode: int
    argv: List[str]
    env_overlay: Dict[str, str] = field(default_factory=dict)
    dry_run: bool = False
    output: str = ""


class CommandRunner:
    """Run external commands; respects INSTALLER_DRY_RUN and tool overrides."""

    def __init__(self, on_event: Optional[LogCallback] = None):
        self.on_event = on_event or (lambda _e: None)
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    @property
    def process(self) -> Optional[subprocess.Popen]:
        return self._proc

    @staticmethod
    def dry_run_enabled() -> bool:
        return os.environ.get("INSTALLER_DRY_RUN", "") in ("1", "true", "yes")

    @staticmethod
    def real_frzr_allowed() -> bool:
        return os.environ.get("INSTALLER_ALLOW_REAL_FRZR", "") in ("1", "true", "yes")

    @staticmethod
    def resolve_tool(default: str, env_key: str) -> str:
        return os.environ.get(env_key, default)

    def emit(self, event: ProgressEvent) -> None:
        self.on_event(event)

    def run(
        self,
        argv: List[str],
        *,
        env: Optional[Dict[str, str]] = None,
        log_file: Optional[str] = None,
        stage: str = "command",
    ) -> RunResult:
        env_full = os.environ.copy()
        overlay = env or {}
        env_full.update(overlay)

        self.emit(ProgressEvent.stage(stage, f"Executing: {' '.join(argv)}"))
        self.emit(ProgressEvent.log(f"=== Executing: {' '.join(argv)} ===\n"))

        if self.dry_run_enabled():
            if not self.real_frzr_allowed() and self._looks_like_frzr(argv):
                # Prefer stub path via env override; if still default binary, synthesize
                pass
            lines = [
                "[DRY-RUN] command not executed\n",
                f"[DRY-RUN] argv: {argv!r}\n",
            ]
            for key in sorted(k for k in overlay if k.startswith("FRZR_") or k == "FRZR_NONINTERACTIVE"):
                lines.append(f"[DRY-RUN] env {key}={overlay[key]}\n")
            text = "".join(lines)
            for line in lines:
                self.emit(ProgressEvent.log(line))
            if log_file:
                os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as fh:
                    fh.write(text)
            self.emit(ProgressEvent.finished(True))
            return RunResult(returncode=0, argv=argv, env_overlay=overlay, dry_run=True, output=text)

        with self._lock:
            self._proc = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env_full,
            )
            proc = self._proc

        output_chunks: List[str] = []
        assert proc.stdout is not None
        if log_file:
            os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
            log_fh = open(log_file, "a", encoding="utf-8")
        else:
            log_fh = None

        try:
            if log_fh:
                log_fh.write(f"\n=== Executing: {' '.join(argv)} ===\n\n")
            for line in proc.stdout:
                output_chunks.append(line)
                if log_fh:
                    log_fh.write(line)
                    log_fh.flush()
                self.emit(ProgressEvent.log(line))
            proc.wait()
        finally:
            if log_fh:
                log_fh.close()
            with self._lock:
                self._proc = None

        ok = proc.returncode == 0
        if ok:
            self.emit(ProgressEvent.finished(True))
        else:
            self.emit(
                ProgressEvent.finished(
                    False, f"command failed (exit {proc.returncode}): {' '.join(argv)}"
                )
            )
        return RunResult(
            returncode=proc.returncode,
            argv=argv,
            env_overlay=overlay,
            dry_run=False,
            output="".join(output_chunks),
        )

    def cancel(self, timeout: float = 5.0) -> None:
        with self._lock:
            proc = self._proc
        if not proc or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    @staticmethod
    def _looks_like_frzr(argv: List[str]) -> bool:
        if not argv:
            return False
        base = os.path.basename(argv[0])
        return base.startswith("frzr-")

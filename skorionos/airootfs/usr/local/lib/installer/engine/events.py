"""Progress events emitted by InstallEngine for any UI to consume."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EventKind(str, Enum):
    STAGE = "stage"
    LOG = "log"
    PROGRESS = "progress"
    FINISHED = "finished"


@dataclass(frozen=True)
class ProgressEvent:
    kind: EventKind
    message: str = ""
    stage: Optional[str] = None
    ratio: Optional[float] = None
    ok: Optional[bool] = None
    error: Optional[str] = None

    @classmethod
    def stage(cls, stage: str, message: str = "") -> "ProgressEvent":
        return cls(kind=EventKind.STAGE, stage=stage, message=message or stage)

    @classmethod
    def log(cls, message: str) -> "ProgressEvent":
        return cls(kind=EventKind.LOG, message=message)

    @classmethod
    def progress(cls, ratio: Optional[float], label: str = "") -> "ProgressEvent":
        return cls(kind=EventKind.PROGRESS, ratio=ratio, message=label)

    @classmethod
    def finished(cls, ok: bool, error: Optional[str] = None) -> "ProgressEvent":
        return cls(kind=EventKind.FINISHED, ok=ok, error=error, message=error or "")

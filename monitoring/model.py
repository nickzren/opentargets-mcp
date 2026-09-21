"""Types shared by the monitoring checks and the alert policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Status(str, Enum):
    """Outcome of a single check.

    UNKNOWN covers every case where the check did not reach a verdict: a
    timeout, a skipped step, an unavailable dependency, a runner failure. It is
    deliberately distinct from PASS, because "nothing went wrong" is not
    evidence that anything went right.
    """

    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CheckResult:
    condition: str
    status: Status
    summary: str
    detail: str = ""


@dataclass(frozen=True)
class IssueSnapshot:
    """The tracking issue for one condition, as it currently stands."""

    number: int
    state: str
    first_failure_at: datetime
    consecutive_failures: int
    acknowledged: bool
    reminded: bool

    @property
    def is_open(self) -> bool:
        return self.state == "open"


class ActionKind(str, Enum):
    NONE = "none"
    OPEN = "open"
    UPDATE = "update"
    REMIND = "remind"
    CLOSE = "close"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    condition: str
    reason: str
    consecutive_failures: int = 0
    issue_number: Optional[int] = None

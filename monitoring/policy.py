"""Alert policy: what to do about a condition, given its latest check.

Pure functions over data, so every rule is testable without touching GitHub or
the network. The rule that matters most is negative: nothing except a
demonstrated PASS may close a tracking issue.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .model import Action, ActionKind, CheckResult, IssueSnapshot, Status

# Acknowledgement means triage — someone has looked — not repair.
ACK_WINDOWS = {
    "package-health": timedelta(hours=48),
    "registry-divergence": timedelta(hours=48),
    "release-lag": timedelta(days=30),
}

DEFAULT_ACK_WINDOW = timedelta(hours=48)


def decide(
    result: CheckResult,
    issue: Optional[IssueSnapshot],
    *,
    now: datetime,
) -> Action:
    """Return the single action to take for this condition."""
    open_issue = issue if issue is not None and issue.is_open else None

    if result.status is Status.PASS:
        if open_issue is None:
            return Action(ActionKind.NONE, result.condition, "healthy, nothing tracked")
        return Action(
            ActionKind.CLOSE,
            result.condition,
            "recovery demonstrated by a passing check",
            consecutive_failures=0,
            issue_number=open_issue.number,
        )

    if result.status is Status.UNKNOWN:
        # No verdict was reached. Hold whatever state exists: never close on
        # the strength of a check that did not run, and never open either.
        if open_issue is None:
            return Action(
                ActionKind.NONE,
                result.condition,
                "status unknown; no verdict, nothing tracked",
            )
        return Action(
            ActionKind.UPDATE,
            result.condition,
            "status unknown; holding the issue open without a verdict",
            consecutive_failures=open_issue.consecutive_failures,
            issue_number=open_issue.number,
        )

    # Status.FAIL
    if open_issue is None:
        return Action(
            ActionKind.OPEN,
            result.condition,
            "first observed failure",
            consecutive_failures=1,
        )

    failures = open_issue.consecutive_failures + 1
    window = ACK_WINDOWS.get(result.condition, DEFAULT_ACK_WINDOW)
    overdue = now - open_issue.first_failure_at > window

    if overdue and not open_issue.acknowledged and not open_issue.reminded:
        return Action(
            ActionKind.REMIND,
            result.condition,
            f"unacknowledged for more than {window}",
            consecutive_failures=failures,
            issue_number=open_issue.number,
        )

    return Action(
        ActionKind.UPDATE,
        result.condition,
        "still failing",
        consecutive_failures=failures,
        issue_number=open_issue.number,
    )

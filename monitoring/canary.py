"""Exercise the write paths a dry run cannot reach.

A dry run returns before any GitHub write, so issue creation, labelling,
assignment, reminder delivery and closure are never proven. The canary drives
the real `decide`/`apply` code through a scripted lifecycle against a clearly
synthetic condition, then inspects the resulting issue directly.

Direct inspection matters: `load_issue` lists only open issues, so its returning
None after a close is indistinguishable from "never existed" or "lookup failed".
Proving closure requires reading back the specific issue number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from .model import ActionKind, CheckResult, IssueSnapshot, Status
from .policy import ACK_WINDOWS, DEFAULT_ACK_WINDOW, decide

CONDITION = "canary"
OVERDUE = ACK_WINDOWS.get(CONDITION, DEFAULT_ACK_WINDOW) + timedelta(hours=1)


@dataclass(frozen=True)
class Step:
    name: str
    result: CheckResult
    offset: timedelta
    expected_kind: ActionKind


def _result(status: Status, summary: str) -> CheckResult:
    return CheckResult(CONDITION, status, summary, "synthetic canary check")


def canary_steps() -> list[Step]:
    """The lifecycle, with the clock advanced rather than waited out."""
    return [
        Step("open", _result(Status.FAIL, "canary failing"),
             timedelta(0), ActionKind.OPEN),
        Step("update", _result(Status.FAIL, "canary still failing"),
             timedelta(minutes=1), ActionKind.UPDATE),
        Step("remind", _result(Status.FAIL, "canary unacknowledged"),
             OVERDUE, ActionKind.REMIND),
        # Past the window again: the reminder must not repeat.
        Step("no-second-reminder", _result(Status.FAIL, "canary still unacknowledged"),
             OVERDUE + timedelta(hours=1), ActionKind.UPDATE),
        # No verdict: the issue must stay open and keep its failure record.
        Step("unknown-holds", _result(Status.UNKNOWN, "canary verdict unavailable"),
             OVERDUE + timedelta(hours=2), ActionKind.UPDATE),
        Step("recover", _result(Status.PASS, "canary recovered"),
             OVERDUE + timedelta(hours=3), ActionKind.CLOSE),
    ]


def snapshot_for(
    number: int,
    first_failure_at: datetime,
    *,
    failures: int,
    reminded: bool = False,
) -> IssueSnapshot:
    return IssueSnapshot(
        number=number,
        state="open",
        first_failure_at=first_failure_at,
        consecutive_failures=failures,
        acknowledged=False,
        reminded=reminded,
    )


def run_canary(
    *,
    now: datetime,
    find_open_canary: Callable[[], Optional[dict]],
    load_issue: Callable[[str], tuple[Optional[IssueSnapshot], Optional[str]]],
    apply_action: Callable[..., Any],
    inspect_issue: Callable[[int], Optional[dict]],
    owner: str = "nickzren",
    label: str = "monitoring",
    load_issue_override: Optional[Callable] = None,
) -> dict:
    """Drive the lifecycle and verify the resulting issue. Never raises."""
    failures: list[str] = []
    steps_run: list[dict] = []
    reader = load_issue_override or load_issue

    existing = find_open_canary()
    if existing:
        return {
            "ok": False,
            "failures": [
                "an open canary issue already exists: "
                f"#{existing.get('number')} {existing.get('url')} — "
                "inspect and close it deliberately; it is not adopted"
            ],
            "steps": [],
        }

    number: Optional[int] = None
    for step in canary_steps():
        issue, error = reader(CONDITION)
        if error:
            failures.append(f"{step.name}: issue lookup failed: {error}")
            break

        action = decide(step.result, issue, now=now + step.offset)
        if action.kind is not step.expected_kind:
            failures.append(
                f"{step.name}: expected {step.expected_kind.value}, "
                f"got {action.kind.value}"
            )
            break

        apply_action(action, step.result, issue, now + step.offset)
        steps_run.append({"step": step.name, "kind": action.kind.value})

        if number is None:
            seen, _ = reader(CONDITION)
            number = seen.number if seen else None

    if failures:
        return {"ok": False, "failures": failures, "steps": steps_run, "issue": number}

    if number is None:
        return {
            "ok": False,
            "failures": ["the canary issue number was never observed"],
            "steps": steps_run,
        }

    failures.extend(_verify_final_state(inspect_issue(number), owner, label))
    return {
        "ok": not failures,
        "failures": failures,
        "steps": steps_run,
        "issue": number,
    }


def _verify_final_state(issue: Optional[dict], owner: str, label: str) -> list[str]:
    """Read the specific issue back; absence of evidence is not success."""
    if not issue:
        return ["could not read the canary issue back; closure is unproven"]

    problems: list[str] = []
    if (issue.get("state") or "").upper() != "CLOSED":
        problems.append(f"final state is {issue.get('state')!r}, expected CLOSED")

    labels = {lab.get("name") for lab in issue.get("labels") or []}
    if label not in labels:
        problems.append(f"label {label!r} missing; found {sorted(labels)}")

    assignees = {a.get("login") for a in issue.get("assignees") or []}
    if owner not in assignees:
        problems.append(f"assignee {owner!r} missing; found {sorted(assignees)}")

    from .cli import REMINDER_COMMENT_MARKER

    marker = REMINDER_COMMENT_MARKER.format(condition=CONDITION)
    delivered = sum(
        1 for c in issue.get("comments") or [] if marker in (c.get("body") or "")
    )
    if delivered != 1:
        problems.append(
            f"expected exactly one marked reminder comment, found {delivered}"
        )
    return problems

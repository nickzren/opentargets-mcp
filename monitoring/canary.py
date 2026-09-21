"""Exercise the write paths a dry run cannot reach.

A dry run returns before any GitHub write, so issue creation, labelling,
assignment, reminder delivery and closure are never proven. The canary drives
the real `decide`/`apply` code through a scripted lifecycle against a clearly
synthetic condition, then inspects the resulting issue directly.

Direct inspection matters: `load_issue` searches only open issues, so after a
close it reports no issue — which is also what it reports when none was ever
created. Proving closure requires reading back the specific issue number.

Selecting the right action does not prove the state it produced, so each step
declares the state that must be observable afterwards, and a write that reported
an error stops the run before any further mutation.
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
    # Choosing an action does not prove the state it produced, so each step
    # declares the state that must be observable afterwards.
    expected_failures: Optional[int] = None
    expected_reminded: bool = False


def _result(status: Status, summary: str) -> CheckResult:
    return CheckResult(CONDITION, status, summary, "synthetic canary check")


def canary_steps() -> list[Step]:
    """The lifecycle, with the clock advanced rather than waited out."""
    return [
        Step("open", _result(Status.FAIL, "canary failing"),
             timedelta(0), ActionKind.OPEN, expected_failures=1),
        Step("update", _result(Status.FAIL, "canary still failing"),
             timedelta(minutes=1), ActionKind.UPDATE, expected_failures=2),
        Step("remind", _result(Status.FAIL, "canary unacknowledged"),
             OVERDUE, ActionKind.REMIND,
             expected_failures=3, expected_reminded=True),
        # Past the window again: the reminder must not repeat.
        Step("no-second-reminder", _result(Status.FAIL, "canary still unacknowledged"),
             OVERDUE + timedelta(hours=1), ActionKind.UPDATE,
             expected_failures=4, expected_reminded=True),
        # No verdict: the issue stays open and the failure record is not reset.
        Step("unknown-holds", _result(Status.UNKNOWN, "canary verdict unavailable"),
             OVERDUE + timedelta(hours=2), ActionKind.UPDATE,
             expected_failures=4, expected_reminded=True),
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
    first_failure_at: Optional[datetime] = None

    for step in canary_steps():
        issue, error = reader(CONDITION)
        if error:
            failures.append(f"{step.name}: issue lookup failed: {error}")
            break

        # Bind to the issue this run created. Searching by condition again could
        # hand a concurrently created issue to apply, and failing afterwards
        # would not undo edits made to the wrong one.
        identity_problem = _same_issue(step.name, "before mutating", issue, number)
        if identity_problem:
            failures.append(identity_problem)
            break

        action = decide(step.result, issue, now=now + step.offset)
        if action.kind is not step.expected_kind:
            failures.append(
                f"{step.name}: expected {step.expected_kind.value}, "
                f"got {action.kind.value}"
            )
            break

        outcome = apply_action(action, step.result, issue, now + step.offset)
        applied_problem = _applied_ok(step.name, outcome)
        if applied_problem:
            # Stop before any further mutation: continuing past a failed write
            # would let the run close an issue it never successfully updated.
            failures.append(applied_problem)
            break

        steps_run.append({"step": step.name, "kind": action.kind.value})

        observed, error = reader(CONDITION)
        if error:
            failures.append(f"{step.name}: read-back failed: {error}")
            break
        if step.expected_kind is ActionKind.OPEN:
            # Identity comes from the creation response only. Falling back to a
            # search would reintroduce the problem the binding exists to
            # prevent: the search can resolve to somebody else's issue.
            number = (
                outcome.get("created_issue") if isinstance(outcome, dict) else None
            )
            if number is None:
                failures.append(
                    f"{step.name}: the creation response did not yield an issue "
                    "number, so identity cannot be established. Stopping before "
                    "any further mutation; nothing is closed, so the created "
                    "issue, if one exists, remains open for inspection."
                )
                break
        if first_failure_at is None and observed is not None:
            first_failure_at = observed.first_failure_at

        identity_problem = _same_issue(step.name, "after read-back", observed, number)
        if identity_problem:
            failures.append(identity_problem)
            break

        state_problems = _verify_step_state(step, observed, first_failure_at)
        if state_problems:
            failures.extend(state_problems)
            break

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


def _same_issue(
    step_name: str,
    when: str,
    issue: Optional[IssueSnapshot],
    number: Optional[int],
) -> Optional[str]:
    """Refuse to touch anything other than the issue this run created."""
    if number is None or issue is None:
        return None
    if issue.number != number:
        return (
            f"{step_name}: {when}, the condition resolved to issue "
            f"#{issue.number}, not the one this run created (#{number}); "
            "refusing to modify it"
        )
    return None


def _applied_ok(step_name: str, outcome: Any) -> Optional[str]:
    """A write that reported an error is not a write that happened."""
    if not isinstance(outcome, dict):
        return f"{step_name}: apply returned {type(outcome).__name__}, not a result"
    if outcome.get("applied") is not True:
        errors = outcome.get("errors") or ["apply did not report success"]
        return f"{step_name}: write failed: {'; '.join(errors)}"
    return None


def _verify_step_state(
    step: Step,
    observed: Optional[IssueSnapshot],
    first_failure_at: Optional[datetime],
) -> list[str]:
    """Read the issue back and check the state the step should have produced."""
    problems: list[str] = []

    if step.expected_kind is ActionKind.CLOSE:
        if observed is not None:
            problems.append(
                f"{step.name}: issue is still open after a close"
            )
        return problems

    if observed is None:
        problems.append(f"{step.name}: the issue is not open after {step.expected_kind.value}")
        return problems

    if step.expected_failures is not None and (
        observed.consecutive_failures != step.expected_failures
    ):
        problems.append(
            f"{step.name}: failure count is {observed.consecutive_failures}, "
            f"expected {step.expected_failures}"
        )
    if observed.reminded is not step.expected_reminded:
        problems.append(
            f"{step.name}: reminded is {observed.reminded}, "
            f"expected {step.expected_reminded}"
        )
    if first_failure_at is not None and observed.first_failure_at != first_failure_at:
        problems.append(
            f"{step.name}: first-failure time changed from {first_failure_at} "
            f"to {observed.first_failure_at}"
        )
    return problems


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

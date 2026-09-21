"""Decision rules for monitoring alerts.

The load-bearing invariant is that only a demonstrated PASS may close an issue.
A check that failed, was skipped, timed out, or could not run is UNKNOWN, and
UNKNOWN must never be recorded as healthy — that is the same mistake as
deriving `blackBoxWarning: false` from a field the query never selected.
"""

from datetime import datetime, timedelta, timezone

import pytest

from monitoring.model import ActionKind, CheckResult, IssueSnapshot, Status
from monitoring.policy import ACK_WINDOWS, decide

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
CONDITION = "package-health"


def result(status, condition=CONDITION):
    return CheckResult(condition=condition, status=status, summary="s", detail="d")


def issue(**kw):
    defaults = dict(
        number=7,
        state="open",
        first_failure_at=NOW - timedelta(hours=1),
        consecutive_failures=1,
        acknowledged=False,
        reminded=False,
    )
    defaults.update(kw)
    return IssueSnapshot(**defaults)


# ---------------------------------------------------------------------------
# Only a demonstrated pass may close
# ---------------------------------------------------------------------------


def test_pass_closes_an_open_issue():
    action = decide(result(Status.PASS), issue(), now=NOW)
    assert action.kind is ActionKind.CLOSE


@pytest.mark.parametrize("status", [Status.FAIL, Status.UNKNOWN])
def test_only_pass_can_close(status):
    action = decide(result(status), issue(), now=NOW)
    assert action.kind is not ActionKind.CLOSE


def test_unknown_holds_an_open_issue_without_closing():
    action = decide(result(Status.UNKNOWN), issue(), now=NOW)
    assert action.kind is ActionKind.UPDATE
    assert "unknown" in action.reason.lower()


def test_unknown_never_opens_an_issue():
    """Unknown does not establish breakage any more than it establishes health."""
    action = decide(result(Status.UNKNOWN), None, now=NOW)
    assert action.kind is ActionKind.NONE


def test_unknown_does_not_reset_the_failure_record():
    snapshot = issue(consecutive_failures=5)
    action = decide(result(Status.UNKNOWN), snapshot, now=NOW)
    assert action.kind is ActionKind.UPDATE
    assert action.consecutive_failures == 5


# ---------------------------------------------------------------------------
# Failure lifecycle
# ---------------------------------------------------------------------------


def test_first_failure_opens_an_issue():
    action = decide(result(Status.FAIL), None, now=NOW)
    assert action.kind is ActionKind.OPEN
    assert action.consecutive_failures == 1


def test_repeat_failure_updates_and_increments():
    action = decide(result(Status.FAIL), issue(consecutive_failures=3), now=NOW)
    assert action.kind is ActionKind.UPDATE
    assert action.consecutive_failures == 4


def test_pass_with_no_open_issue_does_nothing():
    assert decide(result(Status.PASS), None, now=NOW).kind is ActionKind.NONE


def test_closed_issue_is_treated_as_absent():
    action = decide(result(Status.FAIL), issue(state="closed"), now=NOW)
    assert action.kind is ActionKind.OPEN


# ---------------------------------------------------------------------------
# Acknowledgement and the single overdue reminder
# ---------------------------------------------------------------------------


def test_unacknowledged_past_the_window_reminds_once():
    stale = issue(first_failure_at=NOW - ACK_WINDOWS[CONDITION] - timedelta(hours=1))
    action = decide(result(Status.FAIL), stale, now=NOW)
    assert action.kind is ActionKind.REMIND


def test_reminder_is_not_repeated():
    stale = issue(
        first_failure_at=NOW - ACK_WINDOWS[CONDITION] - timedelta(hours=1),
        reminded=True,
    )
    action = decide(result(Status.FAIL), stale, now=NOW)
    assert action.kind is ActionKind.UPDATE


def test_acknowledged_issue_is_not_reminded():
    stale = issue(
        first_failure_at=NOW - ACK_WINDOWS[CONDITION] - timedelta(hours=1),
        acknowledged=True,
    )
    action = decide(result(Status.FAIL), stale, now=NOW)
    assert action.kind is ActionKind.UPDATE


def test_within_the_window_is_not_reminded():
    action = decide(result(Status.FAIL), issue(), now=NOW)
    assert action.kind is ActionKind.UPDATE


def test_unknown_never_triggers_a_reminder():
    stale = issue(first_failure_at=NOW - ACK_WINDOWS[CONDITION] - timedelta(days=5))
    action = decide(result(Status.UNKNOWN), stale, now=NOW)
    assert action.kind is ActionKind.UPDATE


def test_advisory_conditions_get_a_longer_window():
    assert ACK_WINDOWS["release-lag"] > ACK_WINDOWS["package-health"]
    assert ACK_WINDOWS["registry-divergence"] == ACK_WINDOWS["package-health"]

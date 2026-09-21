"""Canary sequence: the write paths a dry run cannot reach.

The canary drives the real decide/apply code through a scripted lifecycle. Its
own safeguards are what these tests pin: read-back must be able to fail, a
pre-existing canary must stop the run, and dry-run must be rejected rather than
silently producing a canary that writes nothing.
"""

from datetime import datetime, timezone

import pytest

from monitoring import canary, cli
from monitoring.model import ActionKind, Status

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


class Recorder:
    """Stands in for the GitHub side, tracking issue state as the real code would."""

    def __init__(self, *, closed_state="CLOSED", labels=("monitoring",),
                 assignees=("nickzren",), reminders=1):
        self.number = 99
        self.issue = None
        self.applied = []
        self._closed_state = closed_state
        self._labels = list(labels)
        self._assignees = list(assignees)
        self._reminders = reminders

    def find_open_canary(self):
        return None

    def load_issue(self, condition):
        return self.issue, None

    def apply_action(self, action, result, issue, now):
        self.applied.append(action.kind)
        if action.kind is ActionKind.OPEN:
            self.issue = canary.snapshot_for(self.number, now, failures=1)
        elif action.kind in (ActionKind.UPDATE, ActionKind.REMIND):
            self.issue = canary.snapshot_for(
                self.number,
                self.issue.first_failure_at,
                failures=action.consecutive_failures,
                reminded=self.issue.reminded or action.kind is ActionKind.REMIND,
            )
        elif action.kind is ActionKind.CLOSE:
            self.issue = None
        return {"kind": action.kind.value}

    def inspect_issue(self, number):
        return {
            "number": number,
            "state": self._closed_state,
            "labels": [{"name": n} for n in self._labels],
            "assignees": [{"login": a} for a in self._assignees],
            "comments": [
                {"body": cli.REMINDER_COMMENT_MARKER.format(condition="canary")}
                for _ in range(self._reminders)
            ],
        }


def run(recorder, **kw):
    return canary.run_canary(
        now=NOW,
        find_open_canary=recorder.find_open_canary,
        load_issue=recorder.load_issue,
        apply_action=recorder.apply_action,
        inspect_issue=recorder.inspect_issue,
        **kw,
    )


# ---------------------------------------------------------------------------
# The happy path, and that it exercises the whole lifecycle
# ---------------------------------------------------------------------------


def test_the_full_lifecycle_passes():
    recorder = Recorder()
    report = run(recorder)
    assert report["ok"] is True
    assert recorder.applied == [
        ActionKind.OPEN,
        ActionKind.UPDATE,
        ActionKind.REMIND,
        ActionKind.UPDATE,
        ActionKind.UPDATE,
        ActionKind.CLOSE,
    ]


def test_the_sequence_covers_unknown_holding_and_pass_closing():
    kinds = [s.expected_kind for s in canary.canary_steps()]
    statuses = [s.result.status for s in canary.canary_steps()]
    assert Status.UNKNOWN in statuses, "must prove UNKNOWN holds the issue open"
    assert kinds[-1] is ActionKind.CLOSE
    assert statuses[-1] is Status.PASS


# ---------------------------------------------------------------------------
# Read-back must be able to fail
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs, missing",
    [
        ({"closed_state": "OPEN"}, "state"),
        ({"labels": ()}, "label"),
        ({"assignees": ()}, "assignee"),
        ({"reminders": 0}, "reminder"),
        ({"reminders": 2}, "reminder"),
    ],
)
def test_read_back_mismatches_fail(kwargs, missing):
    report = run(Recorder(**kwargs))
    assert report["ok"] is False
    assert any(missing in f.lower() for f in report["failures"]), report["failures"]


def test_an_unexpected_action_fails_the_run():
    recorder = Recorder()

    def wrong_load(condition):
        return None, None  # always "no issue", so step 2 would OPEN again

    report = run(recorder, load_issue_override=wrong_load)
    assert report["ok"] is False


def test_a_lookup_error_fails_the_run():
    recorder = Recorder()

    def failing_load(condition):
        return None, "issue lookup failed: 500"

    report = run(recorder, load_issue_override=failing_load)
    assert report["ok"] is False
    assert any("lookup" in f for f in report["failures"])


# ---------------------------------------------------------------------------
# Rerun safety
# ---------------------------------------------------------------------------


def test_an_existing_open_canary_stops_the_run():
    recorder = Recorder()
    recorder.find_open_canary = lambda: {
        "number": 42,
        "url": "https://github.com/x/y/issues/42",
    }
    report = run(recorder)
    assert report["ok"] is False
    assert "42" in str(report["failures"])
    assert recorder.applied == [], "a previous attempt must not be adopted or closed"


# ---------------------------------------------------------------------------
# Dry run is rejected, not silently honoured
# ---------------------------------------------------------------------------


def test_canary_with_dry_run_is_rejected_before_any_write(monkeypatch):
    monkeypatch.setattr(
        cli, "_gh", lambda *a: pytest.fail("no GitHub call may precede the guard")
    )
    code = cli.main(["--canary", "--dry-run"])
    assert code == 2


def test_canary_defaults_to_off():
    parsed = cli.build_parser().parse_args([])
    assert parsed.canary is False


def test_canary_bypasses_normal_reconciliation(monkeypatch):
    monkeypatch.setattr(
        cli,
        "fetch_pypi",
        lambda: pytest.fail("canary must not run health reconciliation"),
    )
    monkeypatch.setattr(cli, "run_canary_mode", lambda: 0)
    assert cli.main(["--canary"]) == 0


def test_workflow_defaults_canary_to_false():
    import pathlib

    workflow = pathlib.Path(".github/workflows/monitor.yml").read_text()
    assert "canary:" in workflow
    assert "default: false" in workflow

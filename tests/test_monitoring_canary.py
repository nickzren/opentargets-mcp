"""Canary sequence: the write paths a dry run cannot reach.

These drive the real `load_issue`, `apply` and `decide` with only the GitHub
operations mocked. That level matters: a harness that supplies the state it is
asked to verify cannot fail, so it would miss a frozen failure count, a reset
count, or a moved first-failure timestamp.
"""

import json
import pathlib
from datetime import datetime, timezone

import pytest

from monitoring import canary, cli
from monitoring.model import Action, ActionKind, CheckResult, Status

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


class FakeGitHub:
    """In-memory `gh`, storing issue bodies so the real parsers round-trip."""

    def __init__(self, *, fail_on=None, corrupt=None, after_create=None):
        self.issues = {}
        self.next_number = 101
        self.calls = []
        self.mutations = []
        self._fail_on = fail_on or {}
        self._corrupt = corrupt
        self._after_create = after_create

    def __call__(self, *args):
        verb = " ".join(args[:2])
        self.calls.append(verb)
        if verb in self._fail_on:
            return False, "", self._fail_on[verb]

        if verb == "issue list":
            open_issues = [i for i in self.issues.values() if i["state"] == "OPEN"]
            return True, json.dumps(open_issues), ""
        if verb == "label create":
            return True, "", ""
        if verb == "issue create":
            number = self.next_number
            self.next_number += 1
            self.issues[number] = {
                "number": number,
                "body": args[args.index("--body") + 1],
                "createdAt": NOW.isoformat(),
                "comments": [],
                "labels": [{"name": cli.LABEL}],
                "assignees": [{"login": cli.OWNER}],
                "state": "OPEN",
                "url": f"https://example.test/{number}",
            }
            if self._after_create:
                self._after_create(self)
            return True, f"https://example.test/repo/issues/{number}\n", ""
        if verb == "issue edit":
            self.mutations.append((verb, int(args[2])))
            issue = self.issues[int(args[2])]
            body = args[args.index("--body") + 1]
            issue["body"] = self._corrupt(body) if self._corrupt else body
            return True, "", ""
        if verb == "issue comment":
            self.mutations.append((verb, int(args[2])))
            self.issues[int(args[2])]["comments"].append(
                {
                    "author": {"login": "github-actions[bot]"},
                    "body": args[args.index("--body") + 1],
                }
            )
            return True, "", ""
        if verb == "issue close":
            self.mutations.append((verb, int(args[2])))
            self.issues[int(args[2])]["state"] = "CLOSED"
            return True, "", ""
        if verb == "issue view":
            return True, json.dumps(self.issues[int(args[2])]), ""
        raise AssertionError(f"unexpected gh call: {args}")


def run_against(fake, monkeypatch):
    """Run the canary through the real lifecycle functions."""
    monkeypatch.setattr(cli, "_gh", fake)
    return canary.run_canary(
        now=NOW,
        find_open_canary=cli.find_open_canary,
        load_issue=cli.load_issue,
        apply_action=lambda action, result, issue, now: cli.apply(
            action, result, issue, now, dry_run=False
        ),
        inspect_issue=cli.inspect_issue,
        owner=cli.OWNER,
        label=cli.LABEL,
    )


# ---------------------------------------------------------------------------
# The happy path, through real state
# ---------------------------------------------------------------------------


def test_the_full_lifecycle_passes(monkeypatch):
    fake = FakeGitHub()
    report = run_against(fake, monkeypatch)
    assert report["ok"] is True, report["failures"]
    assert [s["kind"] for s in report["steps"]] == [
        "open", "update", "remind", "update", "update", "close",
    ]
    issue = fake.issues[report["issue"]]
    assert issue["state"] == "CLOSED"
    marker = cli.REMINDER_COMMENT_MARKER.format(condition="canary")
    assert sum(marker in c["body"] for c in issue["comments"]) == 1


def test_the_sequence_covers_unknown_holding_and_pass_closing():
    steps = canary.canary_steps()
    assert Status.UNKNOWN in [s.result.status for s in steps]
    assert steps[-1].expected_kind is ActionKind.CLOSE
    assert steps[-1].result.status is Status.PASS


def test_the_declared_failure_progression_is_pinned():
    counts = [s.expected_failures for s in canary.canary_steps()]
    assert counts == [1, 2, 3, 4, 4, None], (
        "UNKNOWN must not increment, and must not reset"
    )


# ---------------------------------------------------------------------------
# A failed write must stop the run
# ---------------------------------------------------------------------------


def test_a_failed_update_stops_the_run_before_closing(monkeypatch):
    """A 403 mid-sequence must not yield a closed issue and ok: true."""
    fake = FakeGitHub(fail_on={"issue edit": "HTTP 403: Resource not accessible"})
    report = run_against(fake, monkeypatch)

    assert report["ok"] is False
    assert any("403" in f for f in report["failures"])
    assert "issue close" not in fake.calls, "must not close after a failed write"
    assert fake.issues[report["issue"]]["state"] == "OPEN"


def test_a_failed_creation_stops_the_run(monkeypatch):
    fake = FakeGitHub(fail_on={"issue create": "HTTP 403"})
    report = run_against(fake, monkeypatch)
    assert report["ok"] is False
    assert "issue close" not in fake.calls


def test_a_failed_reminder_comment_stops_the_run(monkeypatch):
    fake = FakeGitHub(fail_on={"issue comment": "HTTP 502"})
    report = run_against(fake, monkeypatch)
    assert report["ok"] is False
    assert "issue close" not in fake.calls


# ---------------------------------------------------------------------------
# Intermediate state invariants
# ---------------------------------------------------------------------------


def _freeze_count(body):
    """Simulate a backend that never advances the failure count."""
    import re

    return re.sub(r"<!-- failures: \d+ -->", "<!-- failures: 1 -->", body)


def _reset_count(body):
    import re

    if "**Status:** unknown" in body:
        return re.sub(r"<!-- failures: \d+ -->", "<!-- failures: 0 -->", body)
    return body


def _move_first_failure(body):
    import re

    return re.sub(
        r"<!-- first-failure: [^ ]+ -->",
        "<!-- first-failure: 2020-01-01T00:00:00+00:00 -->",
        body,
    )


@pytest.mark.parametrize(
    "corrupt, expected",
    [
        (_freeze_count, "failure count"),
        (_reset_count, "failure count"),
        (_move_first_failure, "first-failure time changed"),
    ],
)
def test_state_invariants_are_verified_after_each_step(corrupt, expected, monkeypatch):
    """Choosing the right action does not prove the state it produced."""
    fake = FakeGitHub(corrupt=corrupt)
    report = run_against(fake, monkeypatch)
    assert report["ok"] is False
    assert any(expected in f for f in report["failures"]), report["failures"]


def test_a_reminder_that_does_not_stick_is_caught(monkeypatch):
    def drop_reminder(body):
        return body.replace(cli.REMINDED_MARKER, "")

    fake = FakeGitHub(corrupt=drop_reminder)
    # The comment marker still records delivery, so state stays consistent; the
    # run should still pass, proving deduplication does not rely on the body.
    report = run_against(fake, monkeypatch)
    assert report["ok"] is True, report["failures"]


# ---------------------------------------------------------------------------
# Final read-back
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda i: i.update(labels=[]), "label"),
        (lambda i: i.update(assignees=[]), "assignee"),
        (lambda i: i.update(state="OPEN"), "state"),
    ],
)
def test_final_read_back_mismatches_fail(mutate, expected, monkeypatch):
    fake = FakeGitHub()
    original_view = fake.__call__

    def wrapper(*args):
        ok, out, err = original_view(*args)
        if " ".join(args[:2]) == "issue view" and ok:
            issue = json.loads(out)
            mutate(issue)
            return ok, json.dumps(issue), err
        return ok, out, err

    report = run_against(wrapper, monkeypatch)
    assert report["ok"] is False
    assert any(expected in f.lower() for f in report["failures"]), report["failures"]


def test_an_unreadable_issue_is_not_success(monkeypatch):
    """If the final read fails, closure is unproven — not assumed."""
    fake = FakeGitHub(fail_on={"issue view": "HTTP 500"})
    report = run_against(fake, monkeypatch)
    assert report["ok"] is False
    assert any("unproven" in f for f in report["failures"]), report["failures"]


# ---------------------------------------------------------------------------
# Rerun safety and the dry-run guard
# ---------------------------------------------------------------------------


def test_an_existing_open_canary_stops_the_run(monkeypatch):
    fake = FakeGitHub()
    fake.issues[42] = {
        "number": 42,
        "body": cli.MARKER.format(condition="canary"),
        "createdAt": NOW.isoformat(),
        "comments": [],
        "labels": [{"name": cli.LABEL}],
        "assignees": [],
        "state": "OPEN",
        "url": "https://example.test/42",
    }
    report = run_against(fake, monkeypatch)
    assert report["ok"] is False
    assert "42" in str(report["failures"])
    assert "issue create" not in fake.calls
    assert "issue close" not in fake.calls
    assert fake.issues[42]["state"] == "OPEN", "a prior attempt must not be closed"


def test_canary_with_dry_run_is_rejected_before_any_write(monkeypatch):
    monkeypatch.setattr(
        cli, "_gh", lambda *a: pytest.fail("no GitHub call may precede the guard")
    )
    assert cli.main(["--canary", "--dry-run"]) == 2


def test_canary_defaults_to_off():
    assert cli.build_parser().parse_args([]).canary is False


def test_canary_bypasses_normal_reconciliation(monkeypatch):
    monkeypatch.setattr(
        cli,
        "fetch_pypi",
        lambda: pytest.fail("canary must not run health reconciliation"),
    )
    monkeypatch.setattr(cli, "run_canary_mode", lambda: 0)
    assert cli.main(["--canary"]) == 0


def test_workflow_defaults_canary_to_false():
    workflow = pathlib.Path(".github/workflows/monitor.yml").read_text()
    assert "canary:" in workflow
    assert "default: false" in workflow


# ---------------------------------------------------------------------------
# Later writes must target the issue this run created
# ---------------------------------------------------------------------------


def test_a_rival_issue_receives_no_writes(monkeypatch):
    """A concurrently created match must not be edited, commented or closed."""

    def inject_rival(fake):
        rival = {
            "number": 102,
            "body": cli.MARKER.format(condition="canary"),
            "createdAt": NOW.isoformat(),
            "comments": [],
            "labels": [{"name": cli.LABEL}],
            "assignees": [],
            "state": "OPEN",
            "url": "https://example.test/102",
        }
        # Listed first, so a search by condition would resolve to it.
        fake.issues = {102: rival, **fake.issues}
        fake._after_create = None

    fake = FakeGitHub(after_create=inject_rival)
    report = run_against(fake, monkeypatch)

    assert report["ok"] is False
    assert any("refusing to modify" in f for f in report["failures"]), report["failures"]
    assert all(number != 102 for _, number in fake.mutations), (
        f"the rival issue was modified: {fake.mutations}"
    )
    assert fake.issues[102]["state"] == "OPEN"
    assert fake.issues[102]["comments"] == []


def test_the_created_number_comes_from_the_creation_response(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(cli, "_gh", fake)
    action = Action(ActionKind.OPEN, "canary", "first failure", 1)
    result = CheckResult("canary", Status.FAIL, "failing", "")
    proposed = cli.apply(action, result, None, NOW, dry_run=False)
    assert proposed["created_issue"] == 101


def test_binding_survives_a_rival_appearing_later(monkeypatch):
    """Injected after several steps, not just after creation."""
    state = {"steps": 0}

    def fake_list_hook(fake):
        pass

    fake = FakeGitHub()
    original = fake.__call__

    def wrapper(*args):
        if " ".join(args[:2]) == "issue edit":
            state["steps"] += 1
            if state["steps"] == 2 and 102 not in fake.issues:
                fake.issues = {
                    102: {
                        "number": 102,
                        "body": cli.MARKER.format(condition="canary"),
                        "createdAt": NOW.isoformat(),
                        "comments": [],
                        "labels": [{"name": cli.LABEL}],
                        "assignees": [],
                        "state": "OPEN",
                        "url": "https://example.test/102",
                    },
                    **fake.issues,
                }
        return original(*args)

    report = run_against(wrapper, monkeypatch)
    assert report["ok"] is False
    assert all(number != 102 for _, number in fake.mutations)
    assert fake.issues[102]["state"] == "OPEN"

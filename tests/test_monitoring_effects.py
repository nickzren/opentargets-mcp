"""Effect-layer regressions.

These cover the integration between checks, policy and the GitHub operations —
the seam where a failed lookup can masquerade as "no issue", a failed write as
success, and an ordinary update as a reason to remind again.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from monitoring import cli
from monitoring.checks import EXPECTED_ASSERTIONS, Observation, evaluate_package_health
from monitoring.model import Action, ActionKind, CheckResult, IssueSnapshot, Status

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def snapshot(**kw):
    defaults = dict(
        number=11,
        state="open",
        first_failure_at=NOW - timedelta(days=5),
        consecutive_failures=5,
        acknowledged=False,
        reminded=False,
    )
    defaults.update(kw)
    return IssueSnapshot(**defaults)


def failing(condition="package-health"):
    return CheckResult(condition, Status.FAIL, "assertions failed", "detail here")


# ---------------------------------------------------------------------------
# A failed lookup is not an absent issue
# ---------------------------------------------------------------------------


def test_lookup_failure_is_reported_not_treated_as_absent(monkeypatch):
    monkeypatch.setattr(cli, "_gh", lambda *a: (False, "", "gh: API rate limit"))
    issue, error = cli.load_issue("package-health")
    assert issue is None
    assert error is not None and "rate limit" in error


def test_unparsable_lookup_output_is_an_error(monkeypatch):
    monkeypatch.setattr(cli, "_gh", lambda *a: (True, "not json", ""))
    issue, error = cli.load_issue("package-health")
    assert issue is None
    assert error is not None


def test_successful_lookup_with_no_match_reports_no_error(monkeypatch):
    monkeypatch.setattr(cli, "_gh", lambda *a: (True, "[]", ""))
    issue, error = cli.load_issue("package-health")
    assert issue is None and error is None


def test_main_skips_acting_when_bookkeeping_is_unreliable(monkeypatch, capsys):
    monkeypatch.setattr(cli, "fetch_pypi", lambda: ("0.6.0", NOW, None))
    monkeypatch.setattr(cli, "fetch_registry", lambda: ("0.2.0", "0.2.0", None))
    monkeypatch.setattr(
        cli, "check_package_health", lambda *a, **k: failing()
    )
    monkeypatch.setattr(cli, "load_issue", lambda c: (None, "issue lookup failed: 500"))

    called = []
    monkeypatch.setattr(cli, "apply", lambda *a, **k: called.append(a))

    code = cli.main(["--dry-run"])
    payload = json.loads(capsys.readouterr().out)

    assert called == [], "must not act on unreliable bookkeeping"
    assert all(item["kind"] == "skipped" for item in payload["actions"])
    assert code == 1, "an unreliable run must not report success"


# ---------------------------------------------------------------------------
# Writes are verified
# ---------------------------------------------------------------------------


def test_failed_issue_creation_is_reported(monkeypatch):
    monkeypatch.setattr(cli, "ensure_label", lambda: None)
    monkeypatch.setattr(cli, "_gh", lambda *a: (False, "", "could not create issue"))
    action = Action(ActionKind.OPEN, "package-health", "first failure", 1)
    proposed = cli.apply(action, failing(), None, NOW, dry_run=False)
    assert proposed["applied"] is False
    assert any("create failed" in e for e in proposed["errors"])


def test_missing_label_is_created_before_opening(monkeypatch):
    calls = []

    def fake_gh(*args):
        calls.append(args[0])
        if args[0] == "label":
            return False, "", "could not create label: HTTP 403"
        return True, "", ""

    monkeypatch.setattr(cli, "_gh", fake_gh)
    action = Action(ActionKind.OPEN, "package-health", "first failure", 1)
    proposed = cli.apply(action, failing(), None, NOW, dry_run=False)
    assert "label" in calls
    assert proposed["applied"] is False


def test_existing_label_is_not_an_error(monkeypatch):
    monkeypatch.setattr(
        cli, "_gh", lambda *a: (False, "", 'label "monitoring" already exists')
    )
    assert cli.ensure_label() is None


# ---------------------------------------------------------------------------
# Reminder state survives ordinary updates
# ---------------------------------------------------------------------------


def test_update_preserves_the_reminded_marker():
    """REMIND -> UPDATE -> REMIND would otherwise nag repeatedly."""
    action = Action(ActionKind.UPDATE, "package-health", "still failing", 6, 11)
    proposed = cli.apply(
        action, failing(), snapshot(reminded=True), NOW, dry_run=True
    )
    assert cli.REMINDED_MARKER in proposed["proposed_body"]


def test_reminded_marker_round_trips_through_load(monkeypatch):
    action = Action(ActionKind.REMIND, "package-health", "overdue", 6, 11)
    body = cli.apply(action, failing(), snapshot(), NOW, dry_run=True)[
        "proposed_body"
    ]
    payload = json.dumps(
        [
            {
                "number": 11,
                "body": body,
                "createdAt": NOW.isoformat(),
                "comments": [],
                "labels": [],
            }
        ]
    )
    monkeypatch.setattr(cli, "_gh", lambda *a: (True, payload, ""))
    issue, error = cli.load_issue("package-health")
    assert error is None
    assert issue.reminded is True


def test_first_failure_date_is_carried_forward():
    action = Action(ActionKind.UPDATE, "package-health", "still failing", 6, 11)
    first = NOW - timedelta(days=5)
    proposed = cli.apply(
        action, failing(), snapshot(first_failure_at=first), NOW, dry_run=True
    )
    assert first.isoformat() in proposed["proposed_body"]


# ---------------------------------------------------------------------------
# Dry run must show what it would do
# ---------------------------------------------------------------------------


def test_dry_run_includes_detail_and_body():
    action = Action(ActionKind.OPEN, "package-health", "first failure", 1)
    result = CheckResult(
        "package-health", Status.UNKNOWN, "check did not run", "probe exited 1: boom"
    )
    proposed = cli.apply(action, result, None, NOW, dry_run=True)
    assert proposed["detail"] == "probe exited 1: boom"
    assert "boom" in proposed["proposed_body"]


def test_dry_run_makes_no_writes(monkeypatch):
    monkeypatch.setattr(
        cli, "_gh", lambda *a: pytest.fail("dry run must not call gh")
    )
    action = Action(ActionKind.OPEN, "package-health", "first failure", 1)
    cli.apply(action, failing(), None, NOW, dry_run=True)


# ---------------------------------------------------------------------------
# A tool error is a failed assertion, not an absent verdict
# ---------------------------------------------------------------------------


def test_probe_tool_error_becomes_a_failed_assertion():
    """The original schema break aborted the probe; it must now alert."""
    observations = [
        Observation(EXPECTED_ASSERTIONS[0], False, "tool error: ToolError: Cannot query field"),
        Observation(EXPECTED_ASSERTIONS[1], True),
        Observation(EXPECTED_ASSERTIONS[2], True),
        Observation(EXPECTED_ASSERTIONS[3], True),
    ]
    assert evaluate_package_health(observations).status is Status.FAIL


def test_probe_without_output_is_unknown_with_a_reason(monkeypatch):
    class Done:
        returncode = 1
        stdout = ""
        stderr = "Traceback: boom"

    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: Done())
    monkeypatch.setattr(cli.tempfile, "mkdtemp", lambda prefix="": "/tmp/nope")
    monkeypatch.setattr(cli.shutil, "rmtree", lambda *a, **k: None)
    monkeypatch.setattr(cli.Path, "write_text", lambda self, text: None)

    observations, reason = cli.run_package_probe("0.6.0")
    assert observations is None
    assert reason and "environment setup failed" in reason


# ---------------------------------------------------------------------------
# Retry before alerting
# ---------------------------------------------------------------------------


def test_a_transient_failure_is_not_alerted_when_the_retry_passes(monkeypatch):
    attempts = []

    def fake_probe(version):
        attempts.append(version)
        if len(attempts) == 1:
            return None, "probe could not run: transient"
        return [Observation(name, True) for name in EXPECTED_ASSERTIONS], None

    monkeypatch.setattr(cli, "run_package_probe", fake_probe)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)

    result = cli.check_package_health("0.6.0", None, delay=1)
    assert len(attempts) == 2
    assert result.status is Status.PASS


def test_a_persistent_failure_still_alerts(monkeypatch):
    bad = [Observation(EXPECTED_ASSERTIONS[0], False, "got None")] + [
        Observation(name, True) for name in EXPECTED_ASSERTIONS[1:]
    ]
    monkeypatch.setattr(cli, "run_package_probe", lambda v: (bad, None))
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)

    result = cli.check_package_health("0.6.0", None, delay=1)
    assert result.status is Status.FAIL
    assert "did not clear it" in result.detail


def test_a_passing_probe_is_not_retried(monkeypatch):
    attempts = []

    def fake_probe(version):
        attempts.append(version)
        return [Observation(name, True) for name in EXPECTED_ASSERTIONS], None

    monkeypatch.setattr(cli, "run_package_probe", fake_probe)
    monkeypatch.setattr(
        cli.time, "sleep", lambda s: pytest.fail("a passing probe must not sleep")
    )

    assert cli.check_package_health("0.6.0", None, delay=1).status is Status.PASS
    assert len(attempts) == 1


# ---------------------------------------------------------------------------
# Registry comparison uses the package reference
# ---------------------------------------------------------------------------


def test_registry_fetch_reads_the_pypi_package_version(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_json",
        lambda url: {
            "servers": [
                {
                    "server": {
                        "name": cli.SERVER_NAME,
                        "version": "0.6.0",
                        "packages": [
                            {
                                "registryType": "pypi",
                                "identifier": "opentargets-mcp",
                                "version": "0.2.0",
                            },
                        ],
                    },
                    "_meta": {
                        "io.modelcontextprotocol.registry/official": {"isLatest": True}
                    },
                }
            ]
        },
    )
    manifest, package, reason = cli.fetch_registry()
    assert (manifest, package, reason) == ("0.6.0", "0.2.0", None)


def _registry_payload(packages):
    return {
        "servers": [
            {
                "server": {
                    "name": cli.SERVER_NAME,
                    "version": "0.6.0",
                    "packages": packages,
                },
                "_meta": {
                    "io.modelcontextprotocol.registry/official": {"isLatest": True}
                },
            }
        ]
    }


def test_empty_packages_array_yields_no_package_version(monkeypatch):
    monkeypatch.setattr(cli, "_json", lambda url: _registry_payload([]))
    assert cli.fetch_registry()[1] is None


def test_a_different_package_identifier_is_not_ours(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_json",
        lambda url: _registry_payload(
            [{"registryType": "pypi", "identifier": "something-else", "version": "9.9"}]
        ),
    )
    assert cli.fetch_registry()[1] is None


def test_an_unrunnable_retry_does_not_erase_an_observed_failure(monkeypatch):
    """Only a demonstrated pass clears a failure."""
    bad = [Observation(EXPECTED_ASSERTIONS[0], False, "got None")] + [
        Observation(name, True) for name in EXPECTED_ASSERTIONS[1:]
    ]
    attempts = []

    def fake_probe(version):
        attempts.append(version)
        if len(attempts) == 1:
            return bad, None
        return None, "probe could not run: runner died"

    monkeypatch.setattr(cli, "run_package_probe", fake_probe)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)

    result = cli.check_package_health("0.6.0", None, delay=1)
    assert result.status is Status.FAIL
    assert "got None" in result.detail, "the original diagnostic must survive"
    assert "did not clear it" in result.detail


def test_partial_probe_output_survives_interruption(monkeypatch):
    """A failure observed before cancellation is still a verdict."""
    streamed = (
        '__OBSERVATION__'
        + json.dumps(
            {"name": EXPECTED_ASSERTIONS[0], "ok": False, "detail": "tool error"}
        )
        + "\n"
    )

    class Setup:
        returncode = 0
        stdout = ""
        stderr = b""

    class Killed:
        returncode = -9
        stdout = streamed
        stderr = "Killed"

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        # venv creation and pip install succeed; the probe is then cancelled.
        return Setup() if len(calls) <= 2 else Killed()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli.tempfile, "mkdtemp", lambda prefix="": "/tmp/nope")
    monkeypatch.setattr(cli.shutil, "rmtree", lambda *a, **k: None)
    monkeypatch.setattr(cli.Path, "write_text", lambda self, text: None)

    observations, reason = cli.run_package_probe("0.6.0")
    assert observations and observations[0].ok is False
    assert reason and "exited" in reason
    assert evaluate_package_health(observations).status is Status.FAIL


def test_a_failed_reminder_is_not_recorded_as_delivered(monkeypatch):
    def fake_gh(*args):
        if args[0] == "issue" and args[1] == "comment":
            return False, "", "comment failed"
        return True, "", ""

    monkeypatch.setattr(cli, "_gh", fake_gh)
    action = Action(ActionKind.REMIND, "package-health", "overdue", 6, 11)
    proposed = cli.apply(action, failing(), snapshot(), NOW, dry_run=False)

    assert proposed["applied"] is False
    assert cli.REMINDED_MARKER not in proposed["proposed_body"], (
        "an undelivered reminder must not be marked delivered"
    )


def test_a_delivered_reminder_that_fails_to_record_is_reported(monkeypatch):
    def fake_gh(*args):
        if args[0] == "issue" and args[1] == "edit":
            return False, "", "edit failed"
        return True, "", ""

    monkeypatch.setattr(cli, "_gh", fake_gh)
    action = Action(ActionKind.REMIND, "package-health", "overdue", 6, 11)
    proposed = cli.apply(action, failing(), snapshot(), NOW, dry_run=False)

    assert proposed["applied"] is False
    assert any("comment marker" in e for e in proposed["errors"])


def test_successful_reminder_records_delivery(monkeypatch):
    monkeypatch.setattr(cli, "_gh", lambda *a: (True, "", ""))
    action = Action(ActionKind.REMIND, "package-health", "overdue", 6, 11)
    proposed = cli.apply(action, failing(), snapshot(), NOW, dry_run=False)
    assert proposed["applied"] is True
    assert cli.REMINDED_MARKER in proposed["proposed_body"]


def test_count_assertion_uses_a_small_page():
    """A count wrongly set to the page length must not pass."""
    assert '"page_size": 3' in cli.PROBE_TEMPLATE
    assert "len(rows) == 3 and count > len(rows)" in cli.PROBE_TEMPLATE


def test_workflow_serialises_reconciliation():
    """Lookup and create are separate steps; overlapping runs must queue."""
    import pathlib

    workflow = pathlib.Path(".github/workflows/monitor.yml").read_text()
    assert "concurrency:" in workflow
    assert "cancel-in-progress: false" in workflow, (
        "cancelling mid-write could leave an issue created but unrecorded"
    )


# ---------------------------------------------------------------------------
# Timeouts, truncation, and reminder reconciliation across runs
# ---------------------------------------------------------------------------


def _probe_env(monkeypatch, run):
    monkeypatch.setattr(cli.subprocess, "run", run)
    monkeypatch.setattr(cli.tempfile, "mkdtemp", lambda prefix="": "/tmp/nope")
    monkeypatch.setattr(cli.shutil, "rmtree", lambda *a, **k: None)
    monkeypatch.setattr(cli.Path, "write_text", lambda self, text: None)


def _record(name, ok, detail=""):
    return "__OBSERVATION__" + json.dumps(
        {"name": name, "ok": ok, "detail": detail}
    )


def test_a_timeout_keeps_the_failures_already_observed(monkeypatch):
    """TimeoutExpired carries the child's output; discarding it loses a verdict."""
    streamed = _record(EXPECTED_ASSERTIONS[0], False, "got None") + "\n"

    class Setup:
        returncode = 0
        stdout = ""
        stderr = b""

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if len(calls) <= 2:
            return Setup()
        raise cli.subprocess.TimeoutExpired(
            cmd=cmd, timeout=600, output=streamed, stderr="hung"
        )

    _probe_env(monkeypatch, fake_run)

    observations, reason = cli.run_package_probe("0.6.0")
    assert observations and observations[0].ok is False
    assert reason and "timed out" in reason
    assert evaluate_package_health(observations).status is Status.FAIL


def test_a_truncated_trailing_record_does_not_erase_earlier_failures(monkeypatch):
    streamed = (
        _record(EXPECTED_ASSERTIONS[0], False, "got None")
        + "\n"
        + '__OBSERVATION__{"name": "truncated", "ok"'
        + "\n"
    )

    class Setup:
        returncode = 0
        stdout = ""
        stderr = b""

    class Partial:
        returncode = 1
        stdout = streamed
        stderr = "died"

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Setup() if len(calls) <= 2 else Partial()

    _probe_env(monkeypatch, fake_run)

    observations, reason = cli.run_package_probe("0.6.0")
    assert len(observations) == 1
    assert observations[0].ok is False
    assert "unparsable" in reason
    assert evaluate_package_health(observations).status is Status.FAIL


def test_reminder_is_not_repeated_when_the_body_edit_failed(monkeypatch):
    """Two-run reconciliation: the comment marker is the delivery evidence."""
    delivered = {}

    def run_one(*args):
        if args[0] == "issue" and args[1] == "comment":
            delivered["body"] = args[args.index("--body") + 1]
            return True, "", ""
        if args[0] == "issue" and args[1] == "edit":
            return False, "", "edit failed"
        return True, "", ""

    monkeypatch.setattr(cli, "_gh", run_one)
    action = Action(ActionKind.REMIND, "package-health", "overdue", 6, 11)
    cli.apply(action, failing(), snapshot(), NOW, dry_run=False)
    assert "monitoring-reminder: package-health" in delivered["body"]

    # Second run: the body never got the marker, but the comment did.
    stale_body = cli.issue_body(
        failing(), action, NOW, (NOW - timedelta(days=5)).isoformat(), reminded=False
    )
    payload = json.dumps(
        [
            {
                "number": 11,
                "body": stale_body,
                "createdAt": (NOW - timedelta(days=5)).isoformat(),
                "comments": [
                    {"author": {"login": "github-actions"}, "body": delivered["body"]}
                ],
                "labels": [],
            }
        ]
    )
    monkeypatch.setattr(cli, "_gh", lambda *a: (True, payload, ""))
    issue, error = cli.load_issue("package-health")
    assert error is None
    assert issue.reminded is True, "a delivered reminder must not be sent twice"

    from monitoring.policy import decide

    assert decide(failing(), issue, now=NOW).kind is ActionKind.UPDATE


def test_a_bot_comment_does_not_count_as_acknowledgement(monkeypatch):
    payload = json.dumps(
        [
            {
                "number": 11,
                "body": cli.MARKER.format(condition="package-health"),
                "createdAt": NOW.isoformat(),
                "comments": [
                    {"author": {"login": "github-actions[bot]"}, "body": "reminder"}
                ],
                "labels": [],
            }
        ]
    )
    monkeypatch.setattr(cli, "_gh", lambda *a: (True, payload, ""))
    issue, _ = cli.load_issue("package-health")
    assert issue.acknowledged is False

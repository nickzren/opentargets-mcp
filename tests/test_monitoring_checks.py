"""Check evaluation, especially the difference between failing and not knowing."""

from datetime import datetime, timedelta, timezone

from monitoring.checks import (
    EXPECTED_ASSERTIONS,
    REGISTRY_GRACE,
    Observation,
    evaluate_package_health,
    evaluate_registry_divergence,
)
from monitoring.model import Status

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def all_ok():
    return [Observation(name, True) for name in EXPECTED_ASSERTIONS]


# ---------------------------------------------------------------------------
# Package health
# ---------------------------------------------------------------------------


def test_all_assertions_holding_is_a_pass():
    assert evaluate_package_health(all_ok()).status is Status.PASS


def test_a_failed_assertion_fails():
    obs = all_ok()
    obs[1] = Observation(obs[1].name, False, "got False")
    result = evaluate_package_health(obs)
    assert result.status is Status.FAIL
    assert "got False" in result.detail


def test_a_check_that_did_not_run_is_unknown_not_pass():
    assert evaluate_package_health(None).status is Status.UNKNOWN


def test_partial_results_are_unknown_not_pass():
    """A run that skipped assertions cannot establish health."""
    result = evaluate_package_health(all_ok()[:1])
    assert result.status is Status.UNKNOWN
    assert "did not run" in result.detail


def test_empty_results_are_unknown_not_pass():
    assert evaluate_package_health([]).status is Status.UNKNOWN


# ---------------------------------------------------------------------------
# Registry divergence
# ---------------------------------------------------------------------------


def test_matching_versions_pass():
    result = evaluate_registry_divergence(
        "0.6.0", "0.6.0", pypi_published_at=NOW, now=NOW
    )
    assert result.status is Status.PASS


def test_divergence_within_the_grace_period_passes():
    result = evaluate_registry_divergence(
        "0.5.0",
        "0.6.0",
        pypi_published_at=NOW - timedelta(hours=2),
        now=NOW,
    )
    assert result.status is Status.PASS


def test_divergence_beyond_the_grace_period_fails():
    result = evaluate_registry_divergence(
        "0.5.0",
        "0.6.0",
        pypi_published_at=NOW - REGISTRY_GRACE - timedelta(hours=1),
        now=NOW,
    )
    assert result.status is Status.FAIL


def test_long_standing_divergence_fails():
    """The condition this monitor exists to catch: a year-stale listing."""
    result = evaluate_registry_divergence(
        "0.2.0",
        "0.6.0",
        pypi_published_at=NOW - timedelta(days=365),
        now=NOW,
    )
    assert result.status is Status.FAIL
    assert "0.2.0" in result.summary


def test_unknown_publication_time_does_not_grant_grace():
    result = evaluate_registry_divergence(
        "0.5.0", "0.6.0", pypi_published_at=None, now=NOW
    )
    assert result.status is Status.FAIL


def test_a_failed_lookup_is_unknown_not_pass():
    assert (
        evaluate_registry_divergence(
            None, "0.6.0", pypi_published_at=NOW, now=NOW
        ).status
        is Status.UNKNOWN
    )
    assert (
        evaluate_registry_divergence(
            "0.6.0", None, pypi_published_at=NOW, now=NOW
        ).status
        is Status.UNKNOWN
    )


def test_unknown_carries_the_failure_reason():
    """An UNKNOWN without a reason is untriageable."""
    result = evaluate_package_health(None, reason="probe exited 1: boom")
    assert result.status is Status.UNKNOWN
    assert "boom" in result.detail

    divergence = evaluate_registry_divergence(
        None, "0.6.0", pypi_published_at=NOW, now=NOW, reason="registry 503"
    )
    assert divergence.status is Status.UNKNOWN
    assert "503" in divergence.detail

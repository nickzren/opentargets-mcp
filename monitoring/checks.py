"""Check evaluation.

The effectful parts — installing from PyPI, calling the registry — live in the
CLI. Everything here turns already-gathered observations into a CheckResult, so
the semantics (especially "we could not tell") are unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Sequence

from .model import CheckResult, Status

REGISTRY_GRACE = timedelta(hours=24)

# Positive, observable expectations. An exception-only check would have stayed
# green through the blackBoxWarning defect, so each assertion names a value.
EXPECTED_ASSERTIONS = (
    "search_entities.BRCA1.id == ENSG00000012048",
    "get_drug_info.panitumumab.blackBoxWarning is True",
    # The path that actually regressed: the flag was fabricated as false here
    # while get_drug_info stayed correct, so only this assertion catches it.
    "get_target_known_drugs.EGFR.panitumumab.blackBoxWarning is True",
    "get_target_known_drugs.EGFR.count > page size",
)


@dataclass(frozen=True)
class Observation:
    """One positive assertion and whether it held."""

    name: str
    ok: bool
    detail: str = ""


def evaluate_package_health(
    observations: Optional[Sequence[Observation]],
    *,
    expected: Sequence[str] = EXPECTED_ASSERTIONS,
    reason: Optional[str] = None,
) -> CheckResult:
    """PASS only when every expected assertion ran and held.

    `reason` explains why a check produced no observations. Without it an
    UNKNOWN is untriageable: a transient proxy failure and a genuine break look
    identical in the issue.
    """
    condition = "package-health"

    if observations is None:
        return CheckResult(
            condition,
            Status.UNKNOWN,
            "check did not run",
            reason or "no observations recorded",
        )

    seen = {obs.name for obs in observations}
    missing = [name for name in expected if name not in seen]

    # An observed failure is a verdict. Report it even when other assertions
    # never ran: a known failure must not be hidden by later unavailability.
    failed = [obs for obs in observations if not obs.ok]
    if failed:
        detail = "; ".join(f"{obs.name}: {obs.detail}" for obs in failed)
        if missing:
            detail += " | did not run: " + ", ".join(missing)
        return CheckResult(
            condition,
            Status.FAIL,
            f"{len(failed)} of {len(expected)} assertions failed",
            detail,
        )

    if missing:
        # Nothing failed, but the run is incomplete, so it cannot establish
        # health either.
        return CheckResult(
            condition,
            Status.UNKNOWN,
            "incomplete check",
            "assertions did not run: " + ", ".join(missing),
        )

    return CheckResult(
        condition,
        Status.PASS,
        f"all {len(observations)} assertions held",
    )


def evaluate_registry_divergence(
    registry_version: Optional[str],
    pypi_version: Optional[str],
    *,
    registry_package_version: Optional[str] = None,
    pypi_published_at: Optional[datetime],
    now: datetime,
    grace: timedelta = REGISTRY_GRACE,
    reason: Optional[str] = None,
) -> CheckResult:
    """Compare the advertised registry version against PyPI.

    A release publishes to PyPI first, so a brief divergence is expected. The
    grace period only decides when divergence becomes alert-eligible; it cannot
    stop divergence persisting if nobody acts.
    """
    condition = "registry-divergence"

    if registry_version is None or pypi_version is None:
        which = "registry" if registry_version is None else "PyPI"
        return CheckResult(
            condition,
            Status.UNKNOWN,
            "version lookup failed",
            reason or f"{which} unavailable",
        )

    # The manifest label and the package it points at can disagree; a listing
    # labelled 0.6.0 that references PyPI 0.2.0 still sends users to 0.2.0.
    advertised = {registry_version}
    if registry_package_version is not None:
        advertised.add(registry_package_version)

    if advertised == {pypi_version}:
        return CheckResult(
            condition, Status.PASS, f"both advertise {pypi_version}"
        )

    if pypi_published_at is not None and now - pypi_published_at <= grace:
        # No verdict: publication may still be in flight. UNKNOWN suppresses a
        # new alert without asserting recovery, so an issue tracking an older
        # divergence stays open instead of being closed by an unrelated release.
        return CheckResult(
            condition,
            Status.UNKNOWN,
            f"divergence within the {grace} publication grace period",
            f"registry {registry_version}, PyPI {pypi_version}; not yet a verdict",
        )

    shown = registry_version
    if registry_package_version is not None and registry_package_version != registry_version:
        shown = f"{registry_version} (package {registry_package_version})"
    return CheckResult(
        condition,
        Status.FAIL,
        f"registry advertises {shown}, PyPI has {pypi_version}",
        "discovery through the MCP registry points at the wrong version",
    )

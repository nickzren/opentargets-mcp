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
    "get_drug_info.CHEMBL1201827.blackBoxWarning is True",
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
    if missing:
        # A partial run cannot establish health, so it is not a pass — and it
        # is not a failure either, because the missing assertions never ran.
        return CheckResult(
            condition,
            Status.UNKNOWN,
            "incomplete check",
            "assertions did not run: " + ", ".join(missing),
        )

    failed = [obs for obs in observations if not obs.ok]
    if failed:
        return CheckResult(
            condition,
            Status.FAIL,
            f"{len(failed)} of {len(observations)} assertions failed",
            "; ".join(f"{obs.name}: {obs.detail}" for obs in failed),
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

    if registry_version == pypi_version:
        return CheckResult(
            condition, Status.PASS, f"both advertise {pypi_version}"
        )

    if pypi_published_at is not None and now - pypi_published_at <= grace:
        return CheckResult(
            condition,
            Status.PASS,
            f"divergence within the {grace} publication grace period",
            f"registry {registry_version}, PyPI {pypi_version}",
        )

    return CheckResult(
        condition,
        Status.FAIL,
        f"registry advertises {registry_version}, PyPI has {pypi_version}",
        "discovery through the MCP registry points at the wrong version",
    )

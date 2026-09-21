# Monitoring the published package

Why this exists: between February and September 2026 the package published on
PyPI was broken against the live Open Targets API, while `main` was green. The
fixes existed from 2026-05-04 and were not released for about four and a half
months. Separately, the MCP registry advertised 0.2.0 for a year. Neither
condition was visible to anything that ran in CI, because CI tests `main`.

Green tests on `main` say nothing about whether the published package works.

## Principle

Every check asserts a **positive, observable value**. An exception-only check
would have stayed green through the `blackBoxWarning` defect, where the flag was
derived from a field the query never selected and reported `false` for drugs
that carry a boxed warning.

The corollary is the rule the implementation is built around: a check that
failed, was skipped, timed out, or could not run is **UNKNOWN**, never PASS.
Only a demonstrated pass may close a tracking issue. Absence of evidence is not
evidence of absence.

## Signals

| Condition | Establishes | Does not establish |
|---|---|---|
| `package-health` | Expected behaviour failed in the monitored environment | Whether the cause is the package, upstream, or the runner |
| `registry-divergence` | Publication is out of sync beyond the grace period | That prolonged divergence is impossible — that depends on response |
| `release-lag` *(phase two)* | A release decision needs attention | That a bug fix is waiting to ship |

Phase one implements the first two. Release lag is advisory and follows; its low
implementation cost does not make it the strongest protection for users of the
published package.

### Package health assertions

Run against the package installed from PyPI into an isolated environment:

- `search_entities("BRCA1")` top hit is `ENSG00000012048`
- `get_drug_info("CHEMBL1201827").blackBoxWarning` is `True` (panitumumab)
- `get_target_known_drugs("ENSG00000146648")` reports a `count` above the page size

A partial run — some assertions never executed — is UNKNOWN, not PASS.

## Settled operational values

| Choice | Value |
|---|---|
| Cadence | Daily |
| Registry grace | 24h after PyPI publication |
| Release lag threshold | 14 days from the oldest unreleased package-affecting change, excluding docs/CI-only |
| Owner | `nickzren`, label `monitoring` |
| Acknowledgement | 48h for package health and registry divergence; 30 days for release lag |
| Confirmation | Retry within the same run after 5–10 minutes, not across days |
| Closure | Only on demonstrated recovery |

Acknowledgement means triage — someone has looked — not a promise to repair
within the window.

Confirmation is in-run deliberately: waiting for two consecutive daily failures
would delay confirmation by 24–48 hours after users are already broken.

### UNKNOWN must say why

An UNKNOWN carries the reason it reached no verdict — a lookup exception, a
failed environment build, a probe exit code. Without it, a transient proxy
failure and a genuine break are indistinguishable in the issue, which makes the
alert untriageable. This was found while exercising the checks: a swallowed
exception cost several minutes to diagnose locally, and would cost far more from
an issue body.

## Issue lifecycle

One issue per unresolved condition, updated in place rather than duplicated. The
body carries HTML-comment markers so a later run can find its own bookkeeping:
the condition, the first-failure timestamp, and the consecutive failure count.

- **Open** on first observed failure, assigned to the owner, labelled `monitoring`
- **Update** on repeat failure, incrementing the count so a stale alert visibly
  reads as failing for N runs since a given date
- **Remind** once, and only once, if unacknowledged past the window
- **Close** only when a later check demonstrably passes
- **Hold** on UNKNOWN: the issue stays open, the failure count is not reset, and
  no verdict is recorded

Acknowledgement is any comment from someone other than the bot, or the
`acknowledged` label.

## Known limits

A reminder to the same owner is possible without a second person, but genuine
backup coverage is not. Updating a durable record does not establish that anyone
saw it. This is an organisational limit, not one a workflow can close.

The grace period makes divergence alert-eligible; it cannot prevent divergence
persisting.

## Layout

- `monitoring/model.py` — shared types, including the three-valued `Status`
- `monitoring/policy.py` — pure decision rules
- `monitoring/checks.py` — pure check evaluation
- `monitoring/cli.py` — effects: install, probe, registry lookup, issue writes
- `tests/test_monitoring_policy.py`, `tests/test_monitoring_checks.py`
- `.github/workflows/monitor.yml`

`monitoring/` is outside `src/`, so it does not ship to PyPI.

Phase one is dispatch-only and defaults to a dry run. Enabling the daily
schedule means uncommenting the `schedule` block in the workflow.

# Monitoring the published package

Why this exists: issue #4 reported that the published 0.5.0 failed against Open
Targets 26.06. Fixes for those queries had been on `main` since 2026-05-04 and
were not released for about four and a half months. The exact date the published
package began failing was never established. Separately, the MCP registry
advertised 0.2.0 from 2025-09-22 until 2026-09-21.

CI tests checked-out repository code, not the published artifact. That is a
detection gap, and it is the one this closes. It is not what caused the stale
versions: those were caused by a release that was never cut and a registry
publication that was never run. Monitoring would have surfaced both sooner; it
would not have prevented either.

## Principle

Every check asserts a **positive, observable value**. An exception-only check
would have stayed green through the `blackBoxWarning` defect, where the flag was
derived from a field the query never selected and reported `false` for drugs
that carry a boxed warning.

The corollary is the rule the implementation is built around:

- An **observed assertion failure is FAIL**, and stays FAIL unless a later check
  demonstrates recovery. A subsequent timeout, cancellation or unavailable retry
  does not downgrade it.
- An incomplete or unavailable check with no established failure is **UNKNOWN**:
  insufficient evidence to reach a verdict, in either direction.
- Only **PASS** closes an issue.

Absence of evidence is not evidence of absence — and it is not evidence of
failure either.

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
- `get_drug_info` reports panitumumab's `blackBoxWarning` as `True`
- `get_target_known_drugs` reports it as `True` too — the path that actually
  regressed, while `get_drug_info` stayed correct throughout
- `get_target_known_drugs` reports a `count` above the page size

Assertions run through an MCP client, the way a consumer uses the server, not
against the Python API directly. Each is wrapped individually, so a tool error
is recorded as a failed assertion rather than aborting the run: an aborted probe
would otherwise become UNKNOWN and raise no alert, which is precisely the
failure this monitor exists to catch.

A run where nothing failed but some assertions never executed is UNKNOWN. A run
with an observed failure is FAIL even if later assertions never ran — a known
failure must not be hidden by subsequent unavailability.

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
- **Remind** once, and only once, if unacknowledged past the window. The
  reminder comment carries its own marker, so deduplication rests on the
  delivery itself rather than on a follow-up body edit that may fail
- **Close** only when a later check demonstrably passes
- **Hold** on UNKNOWN: the issue stays open, the failure count is not reset, and
  no verdict is recorded

Acknowledgement is any comment from someone other than the bot, or the
`acknowledged` label.

### Partial and interrupted runs

Observations are streamed as they occur and parsed one record at a time. A
timeout is recovered from the exception, which carries the output the child had
already written. Neither a cancellation, a timeout, nor a truncated trailing
record may erase a failure that was already observed: an all-or-nothing parse or
a discarded timeout buffer would turn an established failure back into silence.

## Known limits

A reminder to the same owner is possible without a second person, but genuine
backup coverage is not. Updating a durable record does not establish that anyone
saw it. This is an organisational limit, not one a workflow can close.

The grace period makes divergence alert-eligible; it cannot prevent divergence
persisting. Within the grace window the result is UNKNOWN rather than PASS:
suppressing a new alert must not assert recovery, or an unrelated release would
close an issue tracking a long-standing divergence.

Divergence compares both the registry manifest version and the PyPI package it
references. A listing labelled 0.6.0 that points at PyPI 0.2.0 still sends users
to 0.2.0.

GitHub bookkeeping is verified rather than assumed. A failed issue lookup is
reported as such and suppresses action for that condition, because treating it
as "no issue exists" would open a duplicate every run; failed writes are
reported and make the run exit non-zero.

Reconciliation is serialised by a workflow `concurrency` group with
`cancel-in-progress: false`. Lookup and creation are separate steps, so two
overlapping runs could otherwise both observe no issue and both create one;
cancelling an in-flight run instead of queueing could leave an issue created but
its bookkeeping unwritten.

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

A dry run returns before any write. It verifies the isolated PyPI installation,
the live assertions, the registry comparison, GitHub reads and the proposed
decisions. GitHub write permissions and the issue lifecycle — creation, label,
comments, closure — are not reached by it.

## Canary

Those write paths are proven by `--canary`, which drives the real `decide` and
`apply` code through a scripted lifecycle against a synthetic `canary`
condition: open, update, remind, confirm the reminder does not repeat, hold on
UNKNOWN, close on PASS. The acknowledgement window is reached by advancing the
clock passed to `decide`, not by waiting.

It runs inside GitHub Actions under `GITHUB_TOKEN` with the same `issues: write`
permission a real alert uses; a local `gh` run would exercise different
credentials and prove less.

Safeguards:

- **Every write is checked, and state is read back after each step.** A write
  that reported an error stops the run before any further mutation: continuing
  would let the canary close an issue it never successfully updated. After each
  step the issue is re-read and its state verified — failure count progressing
  1, 2, 3, 4, 4, the first-failure timestamp unchanged, and the reminder flag —
  because selecting the right action does not prove the state it produced.
- **Every read and write targets the issue this run created.** Once the number
  is known, reads fetch that issue directly rather than searching by condition.
  The first live canary created issue #8, but the immediate label listing did
  not return it; a later listing did. Direct reads remove that dependency on
  listing visibility without assuming a consistency guarantee. The number
  comes from the creation response and from nowhere else — there is no
  fallback to a search, since a search can resolve to somebody else's issue,
  which is the problem the binding exists to prevent. Identity is checked
  before each mutation and after each read-back. If creation yields no usable
  number the run stops immediately, writing nothing further and leaving the
  created issue open for inspection. Re-resolving the condition each step could
  hand a concurrently created issue to `apply`, and failing afterwards would not
  undo edits made to the wrong one.
- **Final read-back is direct.** The canary captures its issue number and
  inspects that issue, because `load_issue` searches only open issues: after a
  close it reports no issue, which is also what it reports when none was ever
  created. Labels, assignment, exactly one marked reminder and the CLOSED state
  are all checked, and any mismatch fails the run.
- **`--canary --dry-run` is rejected** before any write, exit 2. A canary that
  writes nothing proves nothing, so the combination fails loudly rather than
  appearing to succeed. The dispatch must select `canary=true, dry_run=false`
  explicitly. Canary mode bypasses normal health reconciliation.
- **A pre-existing open canary stops the run**, reporting its URL. A previous
  attempt is never adopted or closed automatically.

### What a run leaves behind

A successful run creates one issue, `[monitoring] canary: canary failing`, and
leaves **two** comments on it: the marked reminder and the recovery comment
written on close. Exactly one of those is a reminder, which is what the final
read-back checks. The issue ends CLOSED, and the `monitoring` label is created
permanently if it did not already exist.

The guarantee on failure is that **execution stops as soon as a failure is
detected** — not that the issue is left open. Most failures do leave it open,
because they occur before the close. But if the close succeeds and the final
read-back then fails, the run fails with the issue already closed.

Normal alert discovery still uses a listing. Daily spacing reduces exposure to
short visibility delays, but closely spaced manual runs can encounter them.

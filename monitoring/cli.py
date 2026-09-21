"""Run the monitoring checks and reconcile the tracking issues.

Effects live here; the rules live in `policy` and `checks`.

Two rules shape this module. A path that reaches no verdict must degrade to
UNKNOWN, never to PASS. And a bookkeeping failure — a GitHub call that did not
succeed — must never be reported as successful bookkeeping, because that is the
same mistake one layer up.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .checks import (
    EXPECTED_ASSERTIONS,
    PACKAGE_NAME,
    Observation,
    evaluate_package_health,
    evaluate_registry_divergence,
)
from .model import Action, ActionKind, CheckResult, IssueSnapshot, Status
from .policy import decide

PYPI_JSON = "https://pypi.org/pypi/opentargets-mcp/json"
REGISTRY_SEARCH = (
    "https://registry.modelcontextprotocol.io/v0/servers?search=opentargets&limit=50"
)
SERVER_NAME = "io.github.nickzren/opentargets"
LABEL = "monitoring"
OWNER = "nickzren"
REPO = "nickzren/opentargets-mcp"
# ~7 minutes: long enough for a transient upstream blip to clear, short enough
# that a real failure is not sat on for a day.
RETRY_DELAY_SECONDS = 420

MARKER = "<!-- monitoring-condition: {condition} -->"
REMINDED_MARKER = "<!-- reminded -->"
# Carried in the reminder comment itself. The comment is the delivery, so it is
# the durable evidence; the body marker is a convenience that may fail to write.
REMINDER_COMMENT_MARKER = "<!-- monitoring-reminder: {condition} -->"

# The probe drives the server through MCP, the way a client does, and wraps each
# assertion so a tool error is recorded as a failed assertion rather than
# aborting the run and disappearing into UNKNOWN.
PROBE_TEMPLATE = r'''
import asyncio, json
NAMES = json.loads(r"""__NAMES__""")
obs = []

def record(name, ok, detail=""):
    item = {"name": name, "ok": bool(ok), "detail": str(detail)}
    obs.append(item)
    # Streamed immediately: a run cancelled mid-way must not discard the
    # failures it already observed.
    print("__OBSERVATION__" + json.dumps(item), flush=True)

def payload(result):
    data = getattr(result, "data", None)
    if data is None:
        data = getattr(result, "structured_content", None)
    if data is None:
        texts = [b.text for b in (result.content or []) if getattr(b, "text", None)]
        data = json.loads(texts[-1]) if texts else {}
    return data

async def main():
    from fastmcp import Client
    from opentargets_mcp.server import mcp

    async with Client(mcp) as client:
        try:
            data = payload(await client.call_tool(
                "search_entities",
                {"query_string": "BRCA1", "entity_names": ["target"], "page_size": 1},
            ))
            hits = data["search"]["hits"]
            got = hits[0]["id"] if hits else None
            record(NAMES[0], got == "ENSG00000012048", "got %r" % (got,))
        except Exception as exc:
            record(NAMES[0], False, "tool error: %s: %s" % (type(exc).__name__, exc))

        try:
            data = payload(await client.call_tool(
                "get_drug_info", {"chembl_id": "CHEMBL1201827"}
            ))
            got = data["drug"].get("blackBoxWarning")
            record(NAMES[1], got is True, "got %r" % (got,))
        except Exception as exc:
            record(NAMES[1], False, "tool error: %s: %s" % (type(exc).__name__, exc))

        try:
            data = payload(await client.call_tool(
                "get_target_known_drugs",
                {"ensembl_id": "ENSG00000146648", "page_size": 100},
            ))
            known = data["target"]["knownDrugs"]
            rows = known.get("rows") or []
            pani = [
                r["drug"] for r in rows
                if isinstance(r.get("drug"), dict)
                and r["drug"].get("id") == "CHEMBL1201827"
            ]
            flags = [d.get("blackBoxWarning") for d in pani]
            record(
                NAMES[2],
                bool(flags) and all(f is True for f in flags),
                "rows=%d panitumumab=%d flags=%r" % (len(rows), len(pani), flags),
            )
        except Exception as exc:
            record(NAMES[2], False, "tool error: %s: %s" % (type(exc).__name__, exc))

        try:
            data = payload(await client.call_tool(
                "get_target_known_drugs",
                {"ensembl_id": "ENSG00000146648", "page_size": 3},
            ))
            known = data["target"]["knownDrugs"]
            rows = known.get("rows") or []
            count = known.get("count", 0)
            record(
                NAMES[3],
                len(rows) == 3 and count > len(rows),
                "count=%r rows=%d" % (count, len(rows)),
            )
        except Exception as exc:
            record(NAMES[3], False, "tool error: %s: %s" % (type(exc).__name__, exc))

asyncio.run(main())
'''


def _as_text(stream) -> str:
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode(errors="replace")
    return str(stream)


def _tail(stream, limit: int = 400) -> str:
    """Last bytes of a stream as text, whatever type it arrived as.

    Guarding the type matters: a crash here would replace the real setup
    failure with an AttributeError, hiding the reason the check has no verdict.
    """
    return _as_text(stream)[-limit:]


def _parse_observations(stdout) -> tuple[list[Observation], int]:
    """Parse streamed records one at a time.

    Per-record parsing is deliberate: an all-or-nothing parse would let a
    truncated trailing line erase every valid failure recorded before it.
    """
    marker = "__OBSERVATION__"
    observations: list[Observation] = []
    malformed = 0
    for line in _as_text(stdout).splitlines():
        if not line.startswith(marker):
            continue
        try:
            observations.append(Observation(**json.loads(line[len(marker):])))
        except Exception:  # noqa: BLE001 - counted, and never fatal
            malformed += 1
    return observations, malformed


def _json(url: str):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read())


def fetch_pypi() -> tuple[Optional[str], Optional[datetime], Optional[str]]:
    """Return (version, published_at, failure_reason)."""
    try:
        data = _json(PYPI_JSON)
        version = data["info"]["version"]
        stamps = [
            f["upload_time_iso_8601"] for f in data["releases"].get(version, []) or []
        ]
        published = (
            datetime.fromisoformat(min(stamps).replace("Z", "+00:00"))
            if stamps
            else None
        )
        return version, published, None
    except Exception as exc:  # noqa: BLE001 - reason is reported, not swallowed
        return None, None, f"PyPI lookup failed: {type(exc).__name__}: {exc}"


def fetch_registry() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (manifest_version, pypi_package_version, failure_reason)."""
    try:
        data = _json(REGISTRY_SEARCH)
        for entry in data.get("servers", []):
            server = entry.get("server", {})
            meta = (entry.get("_meta") or {}).get(
                "io.modelcontextprotocol.registry/official", {}
            ) or {}
            if server.get("name") == SERVER_NAME and meta.get("isLatest"):
                packages = server.get("packages") or []
                pypi = next(
                    (
                        p
                        for p in packages
                        if p.get("registryType") == "pypi"
                        and p.get("identifier") == PACKAGE_NAME
                    ),
                    None,
                )
                # A missing entry yields None, which the evaluator treats as
                # "cannot tell" rather than as agreement.
                return server.get("version"), (pypi or {}).get("version"), None
    except Exception as exc:  # noqa: BLE001 - reason is reported, not swallowed
        return None, None, f"registry lookup failed: {type(exc).__name__}: {exc}"
    return None, None, f"registry has no latest entry for {SERVER_NAME}"


def run_package_probe(
    version: str,
) -> tuple[Optional[list[Observation]], Optional[str]]:
    """Install the published package in isolation and drive it through MCP."""
    workdir = Path(tempfile.mkdtemp(prefix="otmcp-monitor-"))
    try:
        venv = workdir / "venv"
        for cmd in (
            [sys.executable, "-m", "venv", str(venv)],
            [
                str(venv / "bin" / "pip"),
                "install",
                "--quiet",
                f"opentargets-mcp=={version}",
            ],
        ):
            done = subprocess.run(cmd, capture_output=True, timeout=900)
            if done.returncode != 0:
                return None, (
                    f"environment setup failed: {cmd[1]}: {_tail(done.stderr)}"
                )

        probe = workdir / "probe.py"
        probe.write_text(
            PROBE_TEMPLATE.replace("__NAMES__", json.dumps(list(EXPECTED_ASSERTIONS)))
        )
        timed_out = False
        try:
            done = subprocess.run(
                [str(venv / "bin" / "python"), str(probe)],
                capture_output=True,
                text=True,
                timeout=600,
            )
            stdout, stderr, returncode = done.stdout, done.stderr, done.returncode
        except subprocess.TimeoutExpired as exc:
            # The exception carries what the child had already written. Losing
            # it would discard failures the probe genuinely observed.
            timed_out = True
            stdout, stderr, returncode = exc.stdout, exc.stderr, None

        observations, malformed = _parse_observations(stdout)
        note = (
            "probe timed out"
            if timed_out
            else (None if returncode == 0 else f"probe exited {returncode}")
        )
        if malformed:
            note = f"{note or 'probe completed'}; {malformed} unparsable record(s)"

        if not observations:
            return None, (
                f"{note or 'probe reported nothing'}: {_tail(stderr)}"
            )
        # Partial output is kept deliberately: whatever was observed before an
        # interruption is evidence, and a failure among it is a verdict.
        return observations, (
            None if note is None else f"{note}: {_tail(stderr)}"
        )
    except Exception as exc:  # noqa: BLE001 - reason is reported, not swallowed
        return None, f"probe could not run: {type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# GitHub bookkeeping. Every call reports whether it actually succeeded.
# ---------------------------------------------------------------------------


def _gh(*args: str) -> tuple[bool, str, str]:
    try:
        done = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=120
        )
    except Exception as exc:  # noqa: BLE001 - reason is reported, not swallowed
        return False, "", f"{type(exc).__name__}: {exc}"
    return done.returncode == 0, done.stdout, (done.stderr or "").strip()


def ensure_label() -> Optional[str]:
    """Create the label if absent. Returns a reason on failure."""
    ok, _, err = _gh(
        "label", "create", LABEL, "--repo", REPO,
        "--description", "Automated monitoring of the published package",
        "--color", "B60205",
    )
    if ok or "already exists" in err.lower():
        return None
    return f"could not ensure label {LABEL!r}: {err}"


def load_issue(condition: str) -> tuple[Optional[IssueSnapshot], Optional[str]]:
    """Return (issue, lookup_error).

    A failed lookup is not the same as "no issue": treating it as absence would
    open a duplicate on every run.
    """
    ok, out, err = _gh(
        "issue", "list", "--repo", REPO, "--label", LABEL, "--state", "open",
        "--json", "number,body,createdAt,comments,labels", "--limit", "50",
    )
    if not ok:
        return None, f"issue lookup failed: {err}"
    try:
        items = json.loads(out)
    except Exception as exc:  # noqa: BLE001 - reason is reported, not swallowed
        return None, f"issue lookup returned unparsable output: {exc}"

    for item in items:
        if MARKER.format(condition=condition) not in (item.get("body") or ""):
            continue
        body = item["body"]
        first = _read_marker(body, "first-failure", item["createdAt"])
        comments = item.get("comments") or []

        def _is_bot(comment):
            login = ((comment.get("author") or {}).get("login") or "").lower()
            return login.startswith("github-actions")

        acknowledged = any(not _is_bot(c) for c in comments) or any(
            lab.get("name") == "acknowledged" for lab in item.get("labels", [])
        )
        # Delivery evidence lives in the comment, so a failed body edit cannot
        # cause a second reminder.
        comment_marker = REMINDER_COMMENT_MARKER.format(condition=condition)
        reminded = REMINDED_MARKER in body or any(
            comment_marker in (c.get("body") or "") for c in comments
        )
        return (
            IssueSnapshot(
                number=item["number"],
                state="open",
                first_failure_at=datetime.fromisoformat(first.replace("Z", "+00:00")),
                consecutive_failures=int(_read_marker(body, "failures", "1")),
                acknowledged=acknowledged,
                reminded=reminded,
            ),
            None,
        )
    return None, None


def _read_marker(body: str, key: str, default: str) -> str:
    token = f"<!-- {key}: "
    if token not in body:
        return default
    return body.split(token, 1)[1].split(" -->", 1)[0]


def issue_body(
    result: CheckResult,
    action: Action,
    now: datetime,
    first: str,
    *,
    reminded: bool,
) -> str:
    lines = [
        MARKER.format(condition=result.condition),
        f"<!-- first-failure: {first} -->",
        f"<!-- failures: {action.consecutive_failures} -->",
    ]
    # Reminder state must survive ordinary updates, or the reminder repeats.
    if reminded:
        lines.append(REMINDED_MARKER)
    lines += [
        "",
        f"**Condition:** `{result.condition}`",
        f"**Status:** {result.status.value}",
        f"**Summary:** {result.summary}",
        f"**Detail:** {result.detail or '—'}",
        "",
        f"First observed failing: {first}",
        f"Consecutive failing runs: {action.consecutive_failures}",
        f"Last checked: {now.isoformat()}",
        "",
        "Acknowledge by commenting here or adding the `acknowledged` label. "
        "Acknowledgement means triage, not repair.",
        "",
        "Closed automatically only when a later run demonstrably passes. "
        "A skipped, timed-out or failed run leaves this open.",
    ]
    return "\n".join(lines)


def apply(
    action: Action,
    result: CheckResult,
    issue: Optional[IssueSnapshot],
    now: datetime,
    *,
    dry_run: bool,
) -> dict:
    first = issue.first_failure_at.isoformat() if issue else now.isoformat()
    # A reminder is only "delivered" once the comment succeeds; presuming it
    # here would suppress every future reminder if delivery failed.
    reminded = bool(issue and issue.reminded)
    body = issue_body(
        result,
        action,
        now,
        first,
        reminded=reminded or action.kind is ActionKind.REMIND,
    )

    proposed = {
        "condition": action.condition,
        "kind": action.kind.value,
        "reason": action.reason,
        "status": result.status.value,
        "summary": result.summary,
        "detail": result.detail,
        "issue": action.issue_number,
        "consecutive_failures": action.consecutive_failures,
        "proposed_body": body if action.kind is not ActionKind.NONE else None,
    }
    if dry_run or action.kind is ActionKind.NONE:
        return proposed

    errors: list[str] = []
    if action.kind is ActionKind.OPEN:
        label_error = ensure_label()
        if label_error:
            errors.append(label_error)
        ok, _, err = _gh(
            "issue", "create", "--repo", REPO,
            "--title", f"[monitoring] {action.condition}: {result.summary}",
            "--body", body, "--label", LABEL, "--assignee", OWNER,
        )
        if not ok:
            errors.append(f"issue create failed: {err}")
    elif action.kind in (ActionKind.UPDATE, ActionKind.REMIND):
        number = str(action.issue_number)
        delivered = reminded
        if action.kind is ActionKind.REMIND:
            ok, _, err = _gh(
                "issue", "comment", number, "--repo", REPO,
                "--body", (
                    REMINDER_COMMENT_MARKER.format(condition=action.condition)
                    + f"\n@{OWNER} still unacknowledged — {action.reason}."
                ),
            )
            if ok:
                delivered = True
            else:
                errors.append(f"reminder comment failed: {err}")
        # Rebuild with the marker reflecting what was actually delivered.
        body = issue_body(result, action, now, first, reminded=delivered)
        ok, _, err = _gh("issue", "edit", number, "--repo", REPO, "--body", body)
        if not ok:
            errors.append(
                "issue edit failed: " + err
                + (
                    " (reminder delivered; deduplication relies on the comment "
                    "marker, not this body)"
                    if delivered and not reminded
                    else ""
                )
            )
        proposed["proposed_body"] = body
    elif action.kind is ActionKind.CLOSE:
        ok, _, err = _gh(
            "issue", "close", str(action.issue_number), "--repo", REPO,
            "--reason", "completed",
            "--comment", f"Recovered: {result.summary}",
        )
        if not ok:
            errors.append(f"issue close failed: {err}")

    proposed["applied"] = not errors
    if errors:
        proposed["errors"] = errors
    return proposed


def check_package_health(
    version: Optional[str], reason: Optional[str], *, delay: int
) -> CheckResult:
    """Probe once, then confirm with a retry before alerting on a non-pass."""
    if version is None:
        return evaluate_package_health(None, reason=reason or "no PyPI version")

    observations, probe_reason = run_package_probe(version)
    first = evaluate_package_health(observations, reason=probe_reason)
    if first.status is Status.PASS or delay < 0:
        return first

    # In-run confirmation: waiting for tomorrow's run would delay a real alert
    # by a day, while alerting immediately fires on every transient blip.
    time.sleep(delay)
    observations, probe_reason = run_package_probe(version)
    retried = evaluate_package_health(observations, reason=probe_reason)

    if first.status is Status.FAIL and retried.status is not Status.PASS:
        # Only a demonstrated pass clears an observed failure. A retry that
        # could not run is not evidence of recovery, and discarding the first
        # diagnostic would leave the failure unalerted.
        return CheckResult(
            first.condition,
            Status.FAIL,
            first.summary,
            f"{first.detail} (retry after {delay}s did not clear it: "
            f"{retried.status.value} — {retried.detail})",
        )

    return CheckResult(
        retried.condition,
        retried.status,
        retried.summary,
        f"{retried.detail} (confirmed by retry after {delay}s; "
        f"first attempt: {first.status.value})",
    )


def find_open_canary() -> Optional[dict]:
    """Return an already-open canary issue, so a rerun stops instead of adopting it."""
    from .canary import CONDITION as CANARY_CONDITION

    ok, out, _ = _gh(
        "issue", "list", "--repo", REPO, "--label", LABEL, "--state", "open",
        "--json", "number,body,url", "--limit", "50",
    )
    if not ok:
        return None
    try:
        items = json.loads(out)
    except Exception:  # noqa: BLE001 - absence of evidence, handled by the caller
        return None
    marker = MARKER.format(condition=CANARY_CONDITION)
    return next(
        (it for it in items if marker in (it.get("body") or "")),
        None,
    )


def inspect_issue(number: int) -> Optional[dict]:
    """Read one issue by number, open or closed.

    load_issue lists only open issues, so it cannot prove a close happened.
    """
    ok, out, _ = _gh(
        "issue", "view", str(number), "--repo", REPO,
        "--json", "number,state,labels,assignees,comments,body",
    )
    if not ok:
        return None
    try:
        return json.loads(out)
    except Exception:  # noqa: BLE001 - unreadable is not verified
        return None


def run_canary_mode() -> int:
    from .canary import run_canary

    report = run_canary(
        now=datetime.now(timezone.utc),
        find_open_canary=find_open_canary,
        load_issue=load_issue,
        apply_action=lambda action, result, issue, now: apply(
            action, result, issue, now, dry_run=False
        ),
        inspect_issue=inspect_issue,
        owner=OWNER,
        label=LABEL,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor the published package.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--canary",
        action="store_true",
        default=False,
        help="exercise the issue lifecycle against a synthetic condition",
    )
    parser.add_argument("--retry-delay", type=int, default=RETRY_DELAY_SECONDS)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.canary:
        if args.dry_run:
            # Refused rather than silently honoured: a canary that writes
            # nothing proves nothing, and the point is to prove the writes.
            print(
                "--canary cannot be combined with --dry-run: the canary exists "
                "to exercise writes. Dispatch with canary=true and dry_run=false."
            )
            return 2
        return run_canary_mode()

    now = datetime.now(timezone.utc)

    pypi_version, pypi_published, pypi_reason = fetch_pypi()
    registry_version, registry_package, registry_reason = fetch_registry()

    results = [
        evaluate_registry_divergence(
            registry_version,
            pypi_version,
            registry_package_version=registry_package,
            pypi_published_at=pypi_published,
            now=now,
            reason=pypi_reason or registry_reason,
        ),
        check_package_health(pypi_version, pypi_reason, delay=args.retry_delay),
    ]

    proposed = []
    for result in results:
        issue, lookup_error = load_issue(result.condition)
        if lookup_error:
            # Bookkeeping is unreliable; acting could duplicate or mis-close.
            proposed.append(
                {
                    "condition": result.condition,
                    "kind": "skipped",
                    "reason": lookup_error,
                    "status": result.status.value,
                    "summary": result.summary,
                    "detail": result.detail,
                }
            )
            continue
        action = decide(result, issue, now=now)
        proposed.append(apply(action, result, issue, now, dry_run=args.dry_run))

    print(json.dumps({"dry_run": args.dry_run, "actions": proposed}, indent=2))
    failed = any(r.status is Status.FAIL for r in results)
    unreliable = any(p.get("kind") == "skipped" or p.get("errors") for p in proposed)
    return 1 if (failed or unreliable) else 0


if __name__ == "__main__":
    raise SystemExit(main())

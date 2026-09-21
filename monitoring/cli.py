"""Run the monitoring checks and reconcile the tracking issues.

Effects live here; the rules live in `policy` and `checks`. Every failure path
must degrade to Status.UNKNOWN rather than to PASS, so a broken runner can
never be mistaken for a healthy package.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .checks import (
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

# Written into the issue body so a later run can find its own bookkeeping.
MARKER = "<!-- monitoring-condition: {condition} -->"

PROBE = r"""
import asyncio, json, sys
obs = []
def record(name, ok, detail=""):
    obs.append({"name": name, "ok": bool(ok), "detail": str(detail)})

async def main():
    from opentargets_mcp.queries import OpenTargetsClient
    from opentargets_mcp.tools.search import SearchApi
    from opentargets_mcp.tools.drug import DrugApi
    from opentargets_mcp.tools.target import TargetApi
    client = OpenTargetsClient()
    try:
        hits = (await SearchApi().search_entities(
            client, "BRCA1", entity_names=["target"], page_size=1))["search"]["hits"]
        got = hits[0]["id"] if hits else None
        record("search_entities.BRCA1.id == ENSG00000012048",
               got == "ENSG00000012048", f"got {got!r}")

        drug = (await DrugApi().get_drug_info(client, "CHEMBL1201827"))["drug"]
        got = drug.get("blackBoxWarning")
        record("get_drug_info.CHEMBL1201827.blackBoxWarning is True",
               got is True, f"got {got!r}")

        known = (await TargetApi().get_target_known_drugs(
            client, "ENSG00000146648", page_size=3))["target"]["knownDrugs"]
        record("get_target_known_drugs.EGFR.count > page size",
               known.get("count", 0) > 3,
               f"count={known.get('count')} rows={len(known.get('rows') or [])}")
    finally:
        await client.close()

asyncio.run(main())
print(json.dumps(obs))
"""


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


def fetch_registry_version() -> tuple[Optional[str], Optional[str]]:
    """Return (version, failure_reason)."""
    try:
        data = _json(REGISTRY_SEARCH)
        for entry in data.get("servers", []):
            server = entry.get("server", {})
            meta = (entry.get("_meta") or {}).get(
                "io.modelcontextprotocol.registry/official", {}
            ) or {}
            if server.get("name") == SERVER_NAME and meta.get("isLatest"):
                return server.get("version"), None
    except Exception as exc:  # noqa: BLE001 - reason is reported, not swallowed
        return None, f"registry lookup failed: {type(exc).__name__}: {exc}"
    return None, f"registry has no latest entry for {SERVER_NAME}"


def run_package_probe(
    version: str,
) -> tuple[Optional[list[Observation]], Optional[str]]:
    """Install the published package in isolation and assert on real values.

    Returns None — meaning UNKNOWN — if the environment could not be built or
    the probe could not report.
    """
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
                tail = (done.stderr or b"")[-400:].decode(errors="replace")
                return None, f"environment setup failed: {cmd[1]}: {tail}"

        probe = workdir / "probe.py"
        probe.write_text(PROBE)
        done = subprocess.run(
            [str(venv / "bin" / "python"), str(probe)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if done.returncode != 0:
            # The probe itself failed to complete: no verdict, not a failure.
            return None, f"probe exited {done.returncode}: {done.stderr[-400:]}"
        payload = json.loads(done.stdout.strip().splitlines()[-1])
        return [Observation(**item) for item in payload], None
    except Exception as exc:  # noqa: BLE001 - reason is reported, not swallowed
        return None, f"probe could not run: {type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# GitHub issue bookkeeping
# ---------------------------------------------------------------------------


def _gh(*args: str) -> Optional[str]:
    done = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=120
    )
    if done.returncode != 0:
        return None
    return done.stdout


def load_issue(condition: str) -> Optional[IssueSnapshot]:
    out = _gh(
        "issue", "list", "--repo", REPO, "--label", LABEL, "--state", "open",
        "--json", "number,body,createdAt,comments,labels", "--limit", "50",
    )
    if out is None:
        return None
    for item in json.loads(out):
        if MARKER.format(condition=condition) not in (item.get("body") or ""):
            continue
        body = item["body"]
        first = _read_marker(body, "first-failure", item["createdAt"])
        count = int(_read_marker(body, "failures", "1"))
        comments = item.get("comments") or []
        acknowledged = any(
            (c.get("author") or {}).get("login") != "github-actions" for c in comments
        ) or any(lab.get("name") == "acknowledged" for lab in item.get("labels", []))
        return IssueSnapshot(
            number=item["number"],
            state="open",
            first_failure_at=datetime.fromisoformat(first.replace("Z", "+00:00")),
            consecutive_failures=count,
            acknowledged=acknowledged,
            reminded="<!-- reminded -->" in body,
        )
    return None


def _read_marker(body: str, key: str, default: str) -> str:
    token = f"<!-- {key}: "
    if token not in body:
        return default
    return body.split(token, 1)[1].split(" -->", 1)[0]


def issue_body(result: CheckResult, action: Action, now: datetime, first: str) -> str:
    return "\n".join(
        [
            MARKER.format(condition=result.condition),
            f"<!-- first-failure: {first} -->",
            f"<!-- failures: {action.consecutive_failures} -->",
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
    )


def apply(action: Action, result: CheckResult, now: datetime, *, dry_run: bool) -> dict:
    proposed = {
        "condition": action.condition,
        "kind": action.kind.value,
        "reason": action.reason,
        "status": result.status.value,
        "summary": result.summary,
        "issue": action.issue_number,
        "consecutive_failures": action.consecutive_failures,
    }
    if dry_run or action.kind is ActionKind.NONE:
        return proposed

    first = now.isoformat()
    if action.kind is ActionKind.OPEN:
        _gh(
            "issue", "create", "--repo", REPO,
            "--title", f"[monitoring] {action.condition}: {result.summary}",
            "--body", issue_body(result, action, now, first),
            "--label", LABEL, "--assignee", OWNER,
        )
    elif action.kind in (ActionKind.UPDATE, ActionKind.REMIND):
        number = str(action.issue_number)
        existing = _gh("issue", "view", number, "--repo", REPO, "--json", "body") or "{}"
        body = json.loads(existing).get("body", "")
        first = _read_marker(body, "first-failure", first)
        new_body = issue_body(result, action, now, first)
        if action.kind is ActionKind.REMIND:
            new_body += "\n<!-- reminded -->"
            _gh(
                "issue", "comment", number, "--repo", REPO,
                "--body", f"@{OWNER} still unacknowledged — {action.reason}.",
            )
        _gh("issue", "edit", number, "--repo", REPO, "--body", new_body)
    elif action.kind is ActionKind.CLOSE:
        _gh(
            "issue", "close", str(action.issue_number), "--repo", REPO,
            "--reason", "completed",
            "--comment", f"Recovered: {result.summary}",
        )
    return proposed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Monitor the published package.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print proposed issue changes without making any",
    )
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)

    pypi_version, pypi_published, pypi_reason = fetch_pypi()
    registry_version, registry_reason = fetch_registry_version()

    results = [
        evaluate_registry_divergence(
            registry_version,
            pypi_version,
            pypi_published_at=pypi_published,
            now=now,
            reason=pypi_reason or registry_reason,
        )
    ]
    if pypi_version is None:
        results.append(
            evaluate_package_health(None, reason=pypi_reason or "no PyPI version")
        )
    else:
        observations, probe_reason = run_package_probe(pypi_version)
        results.append(
            evaluate_package_health(observations, reason=probe_reason)
        )

    proposed = []
    for result in results:
        issue = load_issue(result.condition)
        action = decide(result, issue, now=now)
        proposed.append(apply(action, result, now, dry_run=args.dry_run))

    print(json.dumps({"dry_run": args.dry_run, "actions": proposed}, indent=2))
    # Exit non-zero only when a condition is genuinely failing, so UNKNOWN does
    # not turn a runner problem into a red monitor.
    return 1 if any(r.status is Status.FAIL for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

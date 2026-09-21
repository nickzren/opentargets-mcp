"""Contract tests for clinical-candidate warning flags and pagination.

Two defects motivated these:
  * `drugWarnings` was not selected by several queries, so the derived
    `blackBoxWarning` / `hasBeenWithdrawn` flags were emitted as `False` for
    drugs that genuinely carry warnings (e.g. panitumumab).
  * `promote_clinical_candidates` overwrote the upstream total with the page
    length and always sliced from the start, so callers could not tell a page
    from a complete answer.
"""

import pytest
from fastmcp import Client

import opentargets_mcp.server as server_module
from opentargets_mcp.exceptions import ValidationError
from opentargets_mcp.tools.disease import DiseaseApi
from opentargets_mcp.tools.target import TargetApi
from opentargets_mcp.utils import add_legacy_drug_fields, promote_clinical_candidates

BOXED = {"warningType": "Black Box Warning", "toxicityClass": "dermatological toxicity"}
WITHDRAWN = {"warningType": "Withdrawn", "toxicityClass": "cardiotoxicity"}


# ---------------------------------------------------------------------------
# Warning flags: explicit expected values, not just cross-tool agreement
# ---------------------------------------------------------------------------


def test_boxed_warning_sets_only_black_box_flag():
    drug = add_legacy_drug_fields({"id": "CHEMBL1", "drugWarnings": [BOXED]})
    assert drug["blackBoxWarning"] is True
    assert drug["hasBeenWithdrawn"] is False


def test_withdrawal_sets_only_withdrawn_flag():
    drug = add_legacy_drug_fields({"id": "CHEMBL1", "drugWarnings": [WITHDRAWN]})
    assert drug["hasBeenWithdrawn"] is True
    assert drug["blackBoxWarning"] is False


def test_both_warning_kinds_set_both_flags():
    drug = add_legacy_drug_fields({"id": "CHEMBL1", "drugWarnings": [BOXED, WITHDRAWN]})
    assert drug["blackBoxWarning"] is True
    assert drug["hasBeenWithdrawn"] is True


def test_empty_warning_list_sets_both_flags_false():
    """An empty list is real evidence of no warnings."""
    drug = add_legacy_drug_fields({"id": "CHEMBL1", "drugWarnings": []})
    assert drug["blackBoxWarning"] is False
    assert drug["hasBeenWithdrawn"] is False


def test_absent_warnings_leave_flags_unknown():
    """Never fetched is not the same as none exist."""
    drug = add_legacy_drug_fields({"id": "CHEMBL1"})
    assert "blackBoxWarning" not in drug
    assert "hasBeenWithdrawn" not in drug


def test_null_warnings_leave_flags_unknown():
    drug = add_legacy_drug_fields({"id": "CHEMBL1", "drugWarnings": None})
    assert "blackBoxWarning" not in drug
    assert "hasBeenWithdrawn" not in drug


# ---------------------------------------------------------------------------
# Every query feeding the helper must select the warnings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_path, query_name",
    [
        ("src/opentargets_mcp/tools/target/associations.py", "TargetKnownDrugs"),
        ("src/opentargets_mcp/tools/disease.py", "DiseaseKnownDrugs"),
        ("src/opentargets_mcp/tools/drug/associations.py", "DrugSimilarEntities"),
    ],
)
def test_query_selects_drug_warnings(module_path, query_name):
    import pathlib

    source = pathlib.Path(module_path).read_text()
    assert f"query {query_name}" in source, f"{query_name} not found in {module_path}"
    body = source.split(f"query {query_name}", 1)[1].split('"""', 1)[0]
    assert "drugWarnings" in body, (
        f"{query_name} feeds add_legacy_drug_fields but does not select drugWarnings"
    )


# ---------------------------------------------------------------------------
# Pagination: preserve the upstream total, slice the requested page
# ---------------------------------------------------------------------------


def _candidates(n):
    return {
        "drugAndClinicalCandidates": {
            "count": n,
            "rows": [{"id": f"row{i}", "drug": {"id": f"CHEMBL{i}"}} for i in range(n)],
        }
    }


def test_promote_preserves_upstream_total():
    parent = _candidates(82)
    promote_clinical_candidates(parent, page_index=0, page_size=3)
    assert parent["knownDrugs"]["count"] == 82
    assert len(parent["knownDrugs"]["rows"]) == 3


def test_promote_returns_distinct_pages():
    first = _candidates(82)
    second = _candidates(82)
    promote_clinical_candidates(first, page_index=0, page_size=3)
    promote_clinical_candidates(second, page_index=1, page_size=3)
    assert [r["id"] for r in first["knownDrugs"]["rows"]] == ["row0", "row1", "row2"]
    assert [r["id"] for r in second["knownDrugs"]["rows"]] == ["row3", "row4", "row5"]


def test_promote_page_past_end_is_empty_but_keeps_total():
    parent = _candidates(5)
    promote_clinical_candidates(parent, page_index=10, page_size=3)
    assert parent["knownDrugs"]["rows"] == []
    assert parent["knownDrugs"]["count"] == 5


@pytest.mark.asyncio
async def test_target_known_drugs_passes_page_index_through():
    captured = {}

    class _FakeClient:
        async def _query(self, _query, variables=None):
            captured.update(variables or {})
            return {"target": _candidates(82)}

    result = await TargetApi().get_target_known_drugs(
        _FakeClient(), "ENSG00000146648", page_index=1, page_size=3
    )
    assert result["target"]["knownDrugs"]["count"] == 82
    assert [r["id"] for r in result["target"]["knownDrugs"]["rows"]] == [
        "row3",
        "row4",
        "row5",
    ]


# ---------------------------------------------------------------------------
# Unsupported disease controls must be rejected, not ignored
# ---------------------------------------------------------------------------


class _UnusedClient:
    async def _query(self, _query, variables=None):  # pragma: no cover - must not run
        raise AssertionError("query should not be issued for a rejected argument")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs", [{"cursor": "abc"}, {"free_text_query": "kinase"}]
)
async def test_disease_known_drugs_rejects_unsupported_controls(kwargs):
    with pytest.raises(ValidationError) as exc_info:
        await DiseaseApi().get_disease_known_drugs(
            _UnusedClient(), "MONDO_0004979", **kwargs
        )
    assert next(iter(kwargs)) in str(exc_info.value)


@pytest.mark.asyncio
async def test_rejected_control_reaches_mcp_client_with_useful_text(monkeypatch):
    monkeypatch.setattr(server_module, "get_client", lambda: _UnusedClient())

    async with Client(server_module.mcp) as mcp_client:
        result = await mcp_client.call_tool(
            "get_disease_known_drugs",
            {"efo_id": "MONDO_0004979", "free_text_query": "kinase"},
            raise_on_error=False,
        )

    assert result.is_error
    text = " ".join(
        block.text for block in result.content if getattr(block, "text", None)
    )
    assert "free_text_query" in text

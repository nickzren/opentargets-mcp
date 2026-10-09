"""Offline contract tests for evidence scope and the biomarker filter.

Only Disease.evidences takes `enableIndirect`, and omitting it means indirect,
so both tools must always send it and re-key the result to the `target`
envelope. Live rows carry `biomarkers` dicts of empty lists, which must not
count as biomarker annotations.
"""

import pytest

from opentargets_mcp.tools.evidence import EvidenceApi

BRAF = "ENSG00000157764"
MELANOMA = "MONDO_0005105"
EMPTY_BIOMARKERS = {"geneticVariation": [], "geneExpression": []}


class _RecordingClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def _query(self, query, variables=None):
        self.calls.append((query, variables or {}))
        return self.response


def _disease_evidences(rows, count=100):
    return {"disease": {"evidences": {"count": count, "cursor": "next", "rows": rows}}}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method", ["get_target_disease_evidence", "get_target_disease_biomarkers"]
)
@pytest.mark.parametrize("enable_indirect", [False, True])
async def test_evidence_tools_always_send_enable_indirect(method, enable_indirect):
    client = _RecordingClient(_disease_evidences([]))
    await getattr(EvidenceApi(), method)(
        client, BRAF, MELANOMA, enable_indirect=enable_indirect
    )

    query, variables = client.calls[0]
    assert "disease(efoId: $efoId)" in query
    assert "enableIndirect: $enableIndirect" in query
    assert variables["enableIndirect"] is enable_indirect


@pytest.mark.asyncio
async def test_evidence_defaults_to_direct_and_keeps_target_envelope():
    row = {"id": "ev1", "datasourceId": "eva", "disease": {"id": MELANOMA}}
    client = _RecordingClient(_disease_evidences([row], count=13540))

    result = await EvidenceApi().get_target_disease_evidence(client, BRAF, MELANOMA)

    assert client.calls[0][1]["enableIndirect"] is False
    assert result == {
        "target": {"evidences": {"count": 13540, "cursor": "next", "rows": [row]}}
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method", ["get_target_disease_evidence", "get_target_disease_biomarkers"]
)
async def test_evidence_tools_return_null_target_for_unknown_disease(method):
    result = await getattr(EvidenceApi(), method)(
        _RecordingClient({"disease": None}), BRAF, "MONDO_9999999"
    )
    assert result == {"target": None}


@pytest.mark.asyncio
async def test_biomarker_filter_drops_rows_with_only_empty_annotations():
    rows = [
        {"id": "empty", "biomarkers": EMPTY_BIOMARKERS, "biomarkerList": []},
        {"id": "blank", "biomarkerName": "", "biomarkers": {}, "biomarkerList": None},
        {
            "id": "variant",
            "biomarkers": {**EMPTY_BIOMARKERS, "geneticVariation": [{"id": "V600E"}]},
            "biomarkerList": [],
        },
        {
            "id": "listed",
            "biomarkers": EMPTY_BIOMARKERS,
            "biomarkerList": [{"name": "BRAF V600E"}],
        },
        {"id": "named", "biomarkerName": "BRAF V600E", "biomarkers": EMPTY_BIOMARKERS},
    ]
    client = _RecordingClient(_disease_evidences(rows, count=29))

    result = await EvidenceApi().get_target_disease_biomarkers(client, BRAF, MELANOMA)

    evidences = result["target"]["evidences"]
    assert [row["id"] for row in evidences["rows"]] == ["variant", "listed", "named"]
    assert evidences["count"] == evidences["filteredCount"] == 3
    assert evidences["unfilteredCount"] == 5
    assert evidences["upstreamCount"] == 29
    assert evidences["cursor"] == "next"

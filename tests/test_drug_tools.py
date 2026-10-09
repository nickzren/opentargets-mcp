# tests/test_drug_tools.py
import pathlib

import pytest
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.drug import DrugApi
from opentargets_mcp.tools.target import TargetApi
from .conftest import (
    TEST_DRUG_ID_VEMURAFENIB,
    TEST_DRUG_ID_OSIMERTINIB,
    TEST_TARGET_ID_EGFR,
)

@pytest.mark.asyncio
class TestDrugTools:
    """Tests for tools related to Drugs."""
    drug_api = DrugApi()

    async def test_get_drug_info(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_info(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        assert result["drug"] is not None
        assert result["drug"]["id"] == TEST_DRUG_ID_VEMURAFENIB

    async def test_get_drug_adverse_events(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_adverse_events(client, TEST_DRUG_ID_OSIMERTINIB, page_size=1)
        assert result is not None
        assert "drug" in result
        assert result["drug"] is not None
        assert "adverseEvents" in result["drug"]

    async def test_get_drug_pharmacovigilance(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_pharmacovigilance(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        assert result["drug"] is not None
        assert "hasBeenWithdrawn" in result["drug"]
        assert "adverseEvents" in result["drug"]

    async def test_get_drug_linked_diseases(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_linked_diseases(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        assert result["drug"] is not None
        assert "linkedDiseases" in result["drug"]
        if result["drug"]["linkedDiseases"]:
            assert "count" in result["drug"]["linkedDiseases"]
            assert "rows" in result["drug"]["linkedDiseases"]

    async def test_get_drug_linked_targets(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_linked_targets(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        assert result["drug"] is not None
        assert "linkedTargets" in result["drug"]

    async def test_get_drug_warnings(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_warnings(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        assert result["drug"] is not None
        assert "hasBeenWithdrawn" in result["drug"]
        assert "blackBoxWarning" in result["drug"]

    async def test_get_drug_cross_references(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_cross_references(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        assert result["drug"] is not None
        assert "crossReferences" in result["drug"]

    async def test_get_drug_pharmacogenomics(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_pharmacogenomics(client, TEST_DRUG_ID_OSIMERTINIB, page_size=5)
        assert result is not None
        assert "drug" in result
        assert result["drug"] is not None
        assert "pharmacogenomics" in result["drug"]

    async def test_get_drug_literature_occurrences(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_literature_occurrences(client, TEST_DRUG_ID_VEMURAFENIB, size=5)
        assert result is not None
        assert "drug" in result
        assert result["drug"] is not None
        assert "literatureOcurrences" in result["drug"]

    async def test_get_drug_similar_entities(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_similar_entities(client, TEST_DRUG_ID_VEMURAFENIB, size=5)
        assert result is not None
        assert "drug" in result
        assert result["drug"] is not None
        assert "similarEntities" in result["drug"]


PANITUMUMAB = "CHEMBL1201827"  # Carries a Black Box Warning upstream.


@pytest.mark.asyncio
async def test_warning_flags_agree_across_tool_paths(client: OpenTargetsClient):
    """The known-drugs path must not contradict drug-info on safety flags.

    Both are checked against the known-positive expectation as well as each
    other: two paths sharing a broken helper could agree on the wrong answer.
    """
    info = await DrugApi().get_drug_info(client, PANITUMUMAB)
    info_drug = info["drug"]
    assert info_drug["blackBoxWarning"] is True

    candidates = await TargetApi().get_target_known_drugs(
        client, TEST_TARGET_ID_EGFR, page_size=100
    )
    rows = candidates["target"]["knownDrugs"]["rows"]
    matches = [
        row["drug"]
        for row in rows
        if isinstance(row.get("drug"), dict) and row["drug"].get("id") == PANITUMUMAB
    ]
    assert matches, "panitumumab should appear among EGFR clinical candidates"
    for drug in matches:
        assert drug["blackBoxWarning"] is True
        assert drug["blackBoxWarning"] == info_drug["blackBoxWarning"]
        assert drug["hasBeenWithdrawn"] == info_drug["hasBeenWithdrawn"]


@pytest.mark.asyncio
async def test_known_drugs_count_is_upstream_total(client: OpenTargetsClient):
    """A page must not look like a complete answer."""
    result = await TargetApi().get_target_known_drugs(
        client, TEST_TARGET_ID_EGFR, page_size=3
    )
    known = result["target"]["knownDrugs"]
    assert len(known["rows"]) == 3
    assert known["count"] > 3

    second = await TargetApi().get_target_known_drugs(
        client, TEST_TARGET_ID_EGFR, page_index=1, page_size=3
    )
    first_ids = [row["id"] for row in known["rows"]]
    second_ids = [row["id"] for row in second["target"]["knownDrugs"]["rows"]]
    assert first_ids != second_ids


class _FakeClient:
    def __init__(self, response):
        self.response = response

    async def _query(self, *_args, **_kwargs):
        return self.response


@pytest.mark.parametrize(
    "module_path, query_name",
    [
        ("src/opentargets_mcp/tools/disease.py", "DiseaseSimilarEntities"),
        ("src/opentargets_mcp/tools/drug/associations.py", "DrugSimilarEntities"),
    ],
)
def test_similar_entities_queries_select_every_entity_type(module_path, query_name):
    """Without a fragment, objects of that type come back as a bare `__typename`."""
    source = pathlib.Path(module_path).read_text()
    body = source.split(f"query {query_name}", 1)[1].split('"""', 1)[0]
    for entity_type in ("Target", "Disease", "Drug"):
        assert f"... on {entity_type} {{" in body, f"{query_name} lacks {entity_type}"


@pytest.mark.asyncio
async def test_drug_similar_entities_adds_legacy_fields_only_to_drugs():
    target = {"__typename": "Target", "id": "ENSG00000157764", "approvedSymbol": "BRAF"}
    disease = {"__typename": "Disease", "id": "MONDO_0005105", "name": "melanoma"}
    drug = {
        "__typename": "Drug",
        "id": "CHEMBL3301610",
        "maximumClinicalStage": "APPROVAL",
        "drugWarnings": [],
    }
    response = {
        "drug": {
            "id": TEST_DRUG_ID_VEMURAFENIB,
            "similarEntities": [
                {"score": 0.9, "object": dict(drug)},
                {"score": 0.8, "object": dict(target)},
                {"score": 0.7, "object": dict(disease)},
            ],
        }
    }

    result = await DrugApi().get_drug_similar_entities(
        _FakeClient(response),
        TEST_DRUG_ID_VEMURAFENIB,
        entity_names=["drug", "target", "disease"],
    )

    objects = [row["object"] for row in result["drug"]["similarEntities"]]
    assert objects[0]["isApproved"] is True
    assert objects[0]["maximumClinicalTrialPhase"] == 4
    assert objects[1:] == [target, disease]


@pytest.mark.asyncio
async def test_drug_similar_entities_returns_null_drug_for_unknown_id():
    result = await DrugApi().get_drug_similar_entities(
        _FakeClient({"drug": None}), "CHEMBL999999999"
    )
    assert result == {"drug": None}

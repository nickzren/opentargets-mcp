# tests/test_target_tools.py
import pytest
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.target import TargetApi
from .conftest import TEST_TARGET_ID_BRAF, TEST_TARGET_ID_EGFR # Import shared identifiers

@pytest.mark.asyncio
class TestTargetTools:
    """Tests for tools related to Targets."""
    target_api = TargetApi()

    async def test_get_target_info(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_info(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"): 
            assert result["target"]["id"] == TEST_TARGET_ID_BRAF

    async def test_get_target_associated_diseases(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_associated_diseases(client, TEST_TARGET_ID_EGFR, page_size=1)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "associatedDiseases" in result["target"]
            if result["target"].get("associatedDiseases"):
                assert "rows" in result["target"]["associatedDiseases"]

    async def test_get_target_known_drugs(self, client: OpenTargetsClient):
        ensembl_id = TEST_TARGET_ID_EGFR
        page_size_param_for_function = 2 
        print(f"\n[Test Debug] Testing get_target_known_drugs for {ensembl_id}") 
        result = await self.target_api.get_target_known_drugs(client, ensembl_id, page_size=page_size_param_for_function)
        print(f"[Test Debug] API Result for get_target_known_drugs: {result}") 
        assert result is not None, "API result should not be None"
        assert "target" in result, "Result should contain 'target' key"
        target_data = result.get("target")
        assert target_data is not None, "'target' data should not be None"
        assert "knownDrugs" in target_data, "'target' data should contain 'knownDrugs' key"
        known_drugs_data = target_data.get("knownDrugs")
        assert known_drugs_data is not None, "'knownDrugs' data should not be None"
        assert "count" in known_drugs_data, "'knownDrugs' should have a 'count' field"
        assert "rows" in known_drugs_data, "'knownDrugs' should have a 'rows' field"
        assert isinstance(known_drugs_data["rows"], list), "'rows' should be a list"
        if known_drugs_data["rows"]:
            print(f"[Test Debug] Number of drug rows returned: {len(known_drugs_data['rows'])}")
            first_drug_row = known_drugs_data["rows"][0]
            print(f"[Test Debug] First drug row: {first_drug_row}")
            assert "drugId" in first_drug_row, "Each drug row should have 'drugId'"
            assert "targetId" in first_drug_row, "Each drug row should have 'targetId'"
            if first_drug_row.get("targetId"): 
                 assert first_drug_row["targetId"] == ensembl_id, f"targetId in row should match queried ensembl_id {ensembl_id}"
            assert "drug" in first_drug_row, "Each drug row should have 'drug' object"
            drug_object = first_drug_row.get("drug")
            assert drug_object is not None, "'drug' object in row should not be None"
            assert "id" in drug_object, "'drug' object should have 'id'"
            assert "name" in drug_object, "'drug' object should have 'name'"
            assert "mechanismOfAction" in first_drug_row, "Each drug row should have 'mechanismOfAction'"
            assert "phase" in first_drug_row, "Each drug row should have 'phase'"
            assert "status" in first_drug_row, "Each drug row should have 'status'"
            assert "urls" in first_drug_row, "Each drug row should have 'urls'"
        elif known_drugs_data["count"] == 0:
            print(f"[Test Debug] No known drugs found for {ensembl_id}, which is valid.")
        else:
            assert not (known_drugs_data["count"] > 0 and not known_drugs_data["rows"]), \
                f"knownDrugs count is {known_drugs_data['count']} but no rows returned."


    async def test_get_target_safety_information(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_safety_information(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "safetyLiabilities" in result["target"]

    async def test_get_target_tractability(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_tractability(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "tractability" in result["target"]

    async def test_get_target_expression(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_expression(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "expressions" in result["target"]

    async def test_get_target_genetic_constraint(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_genetic_constraint(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "geneticConstraint" in result["target"]

    async def test_get_target_mouse_phenotypes(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_mouse_phenotypes(client, TEST_TARGET_ID_BRAF, page_size=1)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "mousePhenotypes" in result["target"]

    async def test_get_target_pathways_and_go_terms(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_pathways_and_go_terms(client, TEST_TARGET_ID_BRAF, page_size=1)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "pathways" in result["target"]
            assert "geneOntology" in result["target"]

    async def test_get_target_interactions(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_interactions(client, TEST_TARGET_ID_BRAF, page_size=1)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "interactions" in result["target"]

    async def test_get_target_chemical_probes(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_chemical_probes(client, TEST_TARGET_ID_EGFR) 
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "chemicalProbes" in result["target"]

    async def test_get_target_tep(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_tep(client, "ENSG00000106630") 
        assert result is not None
        assert "target" in result 
        if result.get("target"): 
            assert "tep" in result["target"]

    async def test_get_target_literature_occurrences(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_literature_occurrences(client, TEST_TARGET_ID_BRAF, size=1)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "literatureOcurrences" in result["target"] # Corrected spelling to one 'c'

    async def test_get_target_prioritization(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_prioritization(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "prioritisation" in result["target"]
            if isinstance(result["target"]["prioritisation"], list):
                if result["target"]["prioritisation"]:
                    assert "key" in result["target"]["prioritisation"][0]
                    assert "value" in result["target"]["prioritisation"][0]
            elif isinstance(result["target"]["prioritisation"], dict) and "items" in result["target"]["prioritisation"]:
                if result["target"]["prioritisation"]["items"]:
                    assert "key" in result["target"]["prioritisation"]["items"][0]
                    assert "value" in result["target"]["prioritisation"]["items"][0]


@pytest.mark.asyncio
async def test_client_cache_functionality(client: OpenTargetsClient): 
    """Tests that the client cache returns the same data for identical queries."""
    target_api = TargetApi() 
    result1 = await target_api.get_target_info(client, TEST_TARGET_ID_EGFR)
    result2 = await target_api.get_target_info(client, TEST_TARGET_ID_EGFR)
    
    assert result1 == result2
    if result1 and result1.get("target"): 
        assert result1["target"]["id"] == TEST_TARGET_ID_EGFR

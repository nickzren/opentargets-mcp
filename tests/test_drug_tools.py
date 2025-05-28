# tests/test_drug_tools.py
import pytest
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.drug import DrugApi
from .conftest import TEST_DRUG_ID_VEMURAFENIB, TEST_DRUG_ID_OSIMERTINIB

@pytest.mark.asyncio
class TestDrugTools:
    """Tests for tools related to Drugs."""
    drug_api = DrugApi()

    async def test_get_drug_info(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_info(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        if result.get("drug"):
            assert result["drug"]["id"] == TEST_DRUG_ID_VEMURAFENIB

    async def test_get_drug_adverse_events(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_adverse_events(client, TEST_DRUG_ID_OSIMERTINIB, page_size=1)
        assert result is not None
        assert "drug" in result
        if result.get("drug"):
            assert "adverseEvents" in result["drug"]

    async def test_get_drug_pharmacovigilance(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_pharmacovigilance(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        if result.get("drug"):
            assert "hasBeenWithdrawn" in result["drug"]
            assert "adverseEvents" in result["drug"]

    async def test_get_drug_linked_diseases(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_linked_diseases(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        if result.get("drug"):
            assert "linkedDiseases" in result["drug"]
            if result["drug"]["linkedDiseases"]:
                assert "count" in result["drug"]["linkedDiseases"]
                assert "rows" in result["drug"]["linkedDiseases"]

    async def test_get_drug_linked_targets(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_linked_targets(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        if result.get("drug"):
            assert "linkedTargets" in result["drug"]

    async def test_get_drug_warnings(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_warnings(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        if result.get("drug"):
            assert "hasBeenWithdrawn" in result["drug"]
            assert "blackBoxWarning" in result["drug"]

    async def test_get_drug_cross_references(self, client: OpenTargetsClient):
        result = await self.drug_api.get_drug_cross_references(client, TEST_DRUG_ID_VEMURAFENIB)
        assert result is not None
        assert "drug" in result
        if result.get("drug"):
            assert "crossReferences" in result["drug"]
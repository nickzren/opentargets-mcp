# tests/test_disease_tools.py
import pytest
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.disease import DiseaseApi
from .conftest import TEST_DISEASE_ID_ASTHMA, TEST_DISEASE_ID_MELANOMA

@pytest.mark.asyncio
class TestDiseaseTools:
    """Tests for tools related to Diseases."""
    disease_api = DiseaseApi()

    async def test_get_disease_info(self, client: OpenTargetsClient):
        result = await self.disease_api.get_disease_info(client, TEST_DISEASE_ID_ASTHMA)
        assert result is not None
        assert "disease" in result
        if result.get("disease"):
            assert result["disease"]["id"] == TEST_DISEASE_ID_ASTHMA

    async def test_get_disease_associated_targets(self, client: OpenTargetsClient):
        result = await self.disease_api.get_disease_associated_targets(client, TEST_DISEASE_ID_MELANOMA, page_size=1)
        assert result is not None
        assert "disease" in result
        if result.get("disease"):
            assert "associatedTargets" in result["disease"]
            if result["disease"].get("associatedTargets"):
                assert "rows" in result["disease"]["associatedTargets"]

    async def test_get_disease_phenotypes(self, client: OpenTargetsClient):
        result = await self.disease_api.get_disease_phenotypes(client, TEST_DISEASE_ID_ASTHMA, page_size=1)
        assert result is not None
        assert "disease" in result
        if result.get("disease"):
            assert "phenotypes" in result["disease"]

    async def test_get_disease_otar_projects(self, client: OpenTargetsClient):
        result = await self.disease_api.get_disease_otar_projects(client, "EFO_0005583") # Example: type II diabetes mellitus
        assert result is not None
        assert "disease" in result
        if result.get("disease"):
            assert "otarProjects" in result["disease"]

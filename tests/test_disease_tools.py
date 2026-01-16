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

    async def test_get_disease_known_drugs(self, client: OpenTargetsClient):
        result = await self.disease_api.get_disease_known_drugs(client, TEST_DISEASE_ID_MELANOMA, size=3)
        assert result is not None
        assert "disease" in result
        if result.get("disease"):
            assert "knownDrugs" in result["disease"]
            if result["disease"].get("knownDrugs"):
                assert "count" in result["disease"]["knownDrugs"]
                assert "rows" in result["disease"]["knownDrugs"]

    async def test_get_disease_ontology(self, client: OpenTargetsClient):
        result = await self.disease_api.get_disease_ontology(client, TEST_DISEASE_ID_ASTHMA)
        assert result is not None
        assert "disease" in result
        if result.get("disease"):
            assert "parents" in result["disease"]
            assert "children" in result["disease"]
            assert "therapeuticAreas" in result["disease"]

    async def test_get_disease_literature_occurrences(self, client: OpenTargetsClient):
        result = await self.disease_api.get_disease_literature_occurrences(client, TEST_DISEASE_ID_MELANOMA, size=5)
        assert result is not None
        assert "disease" in result
        if result.get("disease"):
            assert "literatureOcurrences" in result["disease"]

    async def test_get_disease_similar_entities(self, client: OpenTargetsClient):
        result = await self.disease_api.get_disease_similar_entities(client, TEST_DISEASE_ID_ASTHMA, size=5)
        assert result is not None
        assert "disease" in result
        if result.get("disease"):
            assert "similarEntities" in result["disease"]

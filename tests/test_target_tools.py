# tests/test_target_tools.py
import pytest
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.target import TargetApi
from .conftest import TEST_TARGET_ID_BRAF, TEST_TARGET_ID_EGFR

@pytest.mark.asyncio
class TestTargetTools:
    """Tests for all tools related to Targets."""
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
        result = await self.target_api.get_target_known_drugs(client, ensembl_id, page_size=page_size_param_for_function)
        assert result is not None, "API result should not be None"
        assert "target" in result, "Result should contain 'target' key"
        target_data = result.get("target")
        assert target_data is not None, "'target' data should not be None"
        assert "knownDrugs" in target_data, "'target' data should contain 'knownDrugs' key"

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
            assert "literatureOcurrences" in result["target"]

    async def test_get_target_prioritization(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_prioritization(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "prioritisation" in result["target"]

    async def test_get_target_depmap_essentiality(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_depmap_essentiality(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "isEssential" in result["target"]
            assert "depMapEssentiality" in result["target"]

    async def test_get_target_hallmarks(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_hallmarks(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "hallmarks" in result["target"]

    async def test_get_target_homologues(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_homologues(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "homologues" in result["target"]

    async def test_get_target_subcellular_locations(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_subcellular_locations(client, TEST_TARGET_ID_EGFR)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "subcellularLocations" in result["target"]

    async def test_get_target_alternative_genes(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_alternative_genes(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "alternativeGenes" in result["target"]
            assert "transcriptIds" in result["target"]

    async def test_get_target_class(self, client: OpenTargetsClient):
        result = await self.target_api.get_target_class(client, TEST_TARGET_ID_BRAF)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "targetClass" in result["target"]
# tests/test_meta_tools.py
import pytest
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.meta import MetaApi
from .conftest import (
    TEST_DISEASE_ID_ASTHMA,
    TEST_DISEASE_ID_MELANOMA,
    TEST_DRUG_ID_OSIMERTINIB,
    TEST_DRUG_ID_VEMURAFENIB,
    TEST_TARGET_ID_BRAF,
    TEST_TARGET_ID_EGFR,
)

@pytest.mark.asyncio
class TestMetaTools:
    """Tests for metadata and utility tools."""
    meta_api = MetaApi()

    async def test_get_api_metadata(self, client: OpenTargetsClient):
        result = await self.meta_api.get_api_metadata(client)
        assert result is not None
        assert "meta" in result
        if result.get("meta"):
            assert "name" in result["meta"]
            assert "apiVersion" in result["meta"]
            assert "dataVersion" in result["meta"]

    async def test_get_association_datasources(self, client: OpenTargetsClient):
        result = await self.meta_api.get_association_datasources(client)
        assert result is not None
        assert "associationDatasources" in result
        if result.get("associationDatasources"):
            assert isinstance(result["associationDatasources"], list)
            if result["associationDatasources"]:
                assert "datasource" in result["associationDatasources"][0]
                assert "datatype" in result["associationDatasources"][0]

    async def test_get_interaction_resources(self, client: OpenTargetsClient):
        result = await self.meta_api.get_interaction_resources(client)
        assert result is not None
        assert "interactionResources" in result

    async def test_get_gene_ontology_terms(self, client: OpenTargetsClient):
        go_ids = ["GO:0005515", "GO:0008270"]  # protein binding, zinc ion binding
        result = await self.meta_api.get_gene_ontology_terms(client, go_ids)
        assert result is not None
        assert "geneOntologyTerms" in result
        if result.get("geneOntologyTerms"):
            assert isinstance(result["geneOntologyTerms"], list)

    async def test_map_ids(self, client: OpenTargetsClient):
        query_terms = ["BRAF", "melanoma", "vemurafenib"]
        result = await self.meta_api.map_ids(client, query_terms)
        assert result is not None
        assert "mapIds" in result
        if result.get("mapIds"):
            assert "mappings" in result["mapIds"]
            assert "total" in result["mapIds"]

    async def test_map_ids_variant(self, client: OpenTargetsClient):
        query_terms = ["rs699"]
        result = await self.meta_api.map_ids(client, query_terms, entity_names=["variant"])
        assert result is not None
        assert "mapIds" in result
        if result.get("mapIds", {}).get("mappings"):
            hits = result["mapIds"]["mappings"][0].get("hits", [])
            if hits:
                assert hits[0].get("entity") == "variant"

    async def test_map_ids_study(self, client: OpenTargetsClient):
        query_terms = ["asthma"]
        result = await self.meta_api.map_ids(client, query_terms, entity_names=["study"])
        assert result is not None
        assert "mapIds" in result
        if result.get("mapIds", {}).get("mappings"):
            hits = result["mapIds"]["mappings"][0].get("hits", [])
            if hits:
                assert hits[0].get("entity") == "study"

    async def test_get_targets_batch(self, client: OpenTargetsClient):
        result = await self.meta_api.get_targets_batch(client, [TEST_TARGET_ID_BRAF, TEST_TARGET_ID_EGFR])
        assert result is not None
        assert "targets" in result
        if result.get("targets"):
            assert len(result["targets"]) == 2

    async def test_get_diseases_batch(self, client: OpenTargetsClient):
        result = await self.meta_api.get_diseases_batch(client, [TEST_DISEASE_ID_ASTHMA, TEST_DISEASE_ID_MELANOMA])
        assert result is not None
        assert "diseases" in result
        if result.get("diseases"):
            assert len(result["diseases"]) == 2

    async def test_get_drugs_batch(self, client: OpenTargetsClient):
        result = await self.meta_api.get_drugs_batch(client, [TEST_DRUG_ID_VEMURAFENIB, TEST_DRUG_ID_OSIMERTINIB])
        assert result is not None
        assert "drugs" in result
        if result.get("drugs"):
            returned_ids = {drug.get("id") for drug in result["drugs"] if isinstance(drug, dict)}
            assert returned_ids
            assert returned_ids.issubset({TEST_DRUG_ID_VEMURAFENIB, TEST_DRUG_ID_OSIMERTINIB})

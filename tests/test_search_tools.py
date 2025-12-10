# tests/test_search_tools.py
import pytest
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.search import SearchApi
from .conftest import TEST_TARGET_ID_BRAF, TEST_TARGET_ID_EGFR

@pytest.mark.asyncio
class TestSearchTools:
    """Tests for general Search tools, including intelligent resolution and autocomplete features."""
    search_api = SearchApi()

    async def test_search_entities_target(self, client: OpenTargetsClient):
        result = await self.search_api.search_entities(client, "BRAF", entity_names=["target"], page_size=1)
        assert result is not None
        assert "search" in result
        if result.get("search") and result["search"].get("hits"):
            assert result["search"]["hits"][0]["entity"] == "target"

    async def test_search_entities_disease(self, client: OpenTargetsClient):
        result = await self.search_api.search_entities(client, "asthma", entity_names=["disease"], page_size=1)
        assert result is not None
        assert "search" in result
        if result.get("search") and result["search"].get("hits"):
             assert result["search"]["hits"][0]["entity"] == "disease"

    async def test_search_entities_drug(self, client: OpenTargetsClient):
        result = await self.search_api.search_entities(client, "vemurafenib", entity_names=["drug"], page_size=1)
        assert result is not None
        assert "search" in result
        if result.get("search") and result["search"].get("hits"):
            assert result["search"]["hits"][0]["entity"] == "drug"

    async def test_search_entities_multiple(self, client: OpenTargetsClient):
        result = await self.search_api.search_entities(client, "cancer", entity_names=["target", "disease"], page_size=2)
        assert result is not None
        assert "search" in result
        assert "hits" in result["search"]

    async def test_search_entity_resolver(self, client: OpenTargetsClient):
        """
        Tests that searching for a synonym ("ERBB1") correctly resolves to the
        canonical entity ("EGFR") and returns its data.
        """
        result = await self.search_api.search_entities(
            client,
            "ERBB1", # A known synonym for EGFR
            entity_names=["target"]
        )
        assert result is not None
        assert "search" in result
        hits = result.get("search", {}).get("hits", [])
        assert len(hits) > 0
        # Check that the resolver returned the canonical entity (EGFR)
        assert hits[0].get("object", {}).get("id") == TEST_TARGET_ID_EGFR
        assert hits[0].get("object", {}).get("approvedSymbol") == "EGFR"

    async def test_search_suggestions(self, client: OpenTargetsClient):
        if not self.search_api.fuzzy_process:
            pytest.skip("'thefuzz' library not installed, skipping suggestion test.")

        result = await self.search_api.search_suggestions(
            client,
            "vemur",
            entity_names=["drug"]
        )
        assert result is not None
        assert "suggestions" in result
        suggestions = result.get("suggestions", [])
        assert len(suggestions) > 0
        assert "vemurafenib" in suggestions[0].get("label", "").lower()
        assert suggestions[0].get("entity") == "drug"

    async def test_get_similar_targets(self, client: OpenTargetsClient):
        result = await self.search_api.get_similar_targets(client, TEST_TARGET_ID_BRAF, size=1)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "similarEntities" in result["target"]

    async def test_search_facets(self, client: OpenTargetsClient):
        result = await self.search_api.search_facets(client, query_string="cancer", page_size=1)
        assert result is not None
        assert "facets" in result
        if result.get("facets"):
            assert "categories" in result["facets"]
            assert "hits" in result["facets"]

    async def test_search_entities_variant(self, client: OpenTargetsClient):
        result = await self.search_api.search_entities(client, "rs699", entity_names=["variant"], page_size=1)
        assert result is not None
        assert "search" in result
        if result.get("search") and result["search"].get("hits"):
            assert result["search"]["hits"][0]["entity"] == "variant"
            obj = result["search"]["hits"][0].get("object", {})
            assert "chromosome" in obj or "position" in obj

    async def test_search_entities_study(self, client: OpenTargetsClient):
        result = await self.search_api.search_entities(client, "asthma", entity_names=["study"], page_size=1)
        assert result is not None
        assert "search" in result
        if result.get("search") and result["search"].get("hits"):
            assert result["search"]["hits"][0]["entity"] == "study"
            obj = result["search"]["hits"][0].get("object", {})
            assert "studyType" in obj or "traitFromSource" in obj
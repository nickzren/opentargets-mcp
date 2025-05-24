# tests/test_search_tools.py
import pytest
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.search import SearchApi
from .conftest import TEST_TARGET_ID_BRAF

@pytest.mark.asyncio
class TestSearchTools:
    """Tests for general Search tools."""
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

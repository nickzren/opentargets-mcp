import pytest
import asyncio
from opentargets_mcp.queries import OpenTargetsClient


@pytest.mark.asyncio
async def test_search_targets():
    client = OpenTargetsClient()
    try:
        result = await client.search_targets("BRAF", size=5)
        assert "search" in result
        assert "hits" in result["search"]
        assert len(result["search"]["hits"]) <= 5
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_target_info():
    client = OpenTargetsClient()
    try:
        result = await client.get_target_info("ENSG00000157764")
        assert "target" in result
        assert result["target"]["approvedSymbol"] == "BRAF"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_search_diseases():
    client = OpenTargetsClient()
    try:
        result = await client.search_diseases("lung cancer", size=3)
        assert "search" in result
        assert "hits" in result["search"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_disease_targets():
    client = OpenTargetsClient()
    try:
        # Note: we fixed the tool definition for this function earlier.
        # This test passes the argument positionally, so it was not affected.
        result = await client.get_disease_targets("EFO_0000270", size=5)
        assert "disease" in result
        if result["disease"]:  # Check if disease is not None
            assert "associatedTargets" in result["disease"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cache_functionality():
    client = OpenTargetsClient()
    try:
        # First call - should hit the API
        result1 = await client.search_targets("TP53", size=1)
        
        # Second call - should use cache
        result2 = await client.search_targets("TP53", size=1)
        
        # Results should be identical
        assert result1 == result2
    finally:
        await client.close()
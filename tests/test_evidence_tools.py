# tests/test_evidence_tools.py
import pytest
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.evidence import EvidenceApi
from .conftest import TEST_TARGET_ID_BRAF, TEST_TARGET_ID_EGFR, TEST_DISEASE_ID_MELANOMA

@pytest.mark.asyncio
class TestEvidenceTools:
    """Tests for tools related to Evidence."""
    evidence_api = EvidenceApi()

    async def test_get_target_disease_evidence(self, client: OpenTargetsClient):
        result = await self.evidence_api.get_target_disease_evidence(client, TEST_TARGET_ID_BRAF, TEST_DISEASE_ID_MELANOMA, size=1)
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "evidences" in result["target"]
            if result["target"].get("evidences"):
                assert "rows" in result["target"]["evidences"]

    async def test_get_target_disease_biomarkers(self, client: OpenTargetsClient):
        result = await self.evidence_api.get_target_disease_biomarkers(client, TEST_TARGET_ID_EGFR, "EFO_0003060", size=1) # EGFR and NSCLC
        assert result is not None
        assert "target" in result
        if result.get("target"):
            assert "evidences" in result["target"]
            if result["target"].get("evidences"):
                assert "rows" in result["target"]["evidences"]

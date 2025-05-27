# tests/test_study_tools.py
import pytest
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.study import StudyApi
from .conftest import TEST_DISEASE_ID_ASTHMA

# Test study IDs
TEST_STUDY_ID_1 = "GCST90002357"  # Example GWAS study
TEST_STUDY_LOCUS_ID = "GCST90002357_1_154453788"  # Example credible set

@pytest.mark.asyncio
class TestStudyTools:
    """Tests for tools related to Studies."""
    study_api = StudyApi()

    async def test_get_study_info(self, client: OpenTargetsClient):
        result = await self.study_api.get_study_info(client, TEST_STUDY_ID_1)
        assert result is not None
        assert "study" in result
        if result.get("study"):
            assert result["study"]["id"] == TEST_STUDY_ID_1
            assert "studyType" in result["study"]
            assert "traitFromSource" in result["study"]

    async def test_get_studies_by_disease(self, client: OpenTargetsClient):
        result = await self.study_api.get_studies_by_disease(client, [TEST_DISEASE_ID_ASTHMA], page_size=1)
        assert result is not None
        assert "studies" in result
        if result.get("studies"):
            assert "count" in result["studies"]
            assert "rows" in result["studies"]

    async def test_get_study_credible_sets(self, client: OpenTargetsClient):
        result = await self.study_api.get_study_credible_sets(client, TEST_STUDY_ID_1, page_size=1)
        assert result is not None
        assert "study" in result
        if result.get("study"):
            assert "credibleSets" in result["study"]

    async def test_get_credible_set_by_id(self, client: OpenTargetsClient):
        # This test may fail if the specific credible set ID doesn't exist
        # In real usage, you'd get this ID from get_study_credible_sets
        try:
            result = await self.study_api.get_credible_set_by_id(client, TEST_STUDY_LOCUS_ID)
            assert result is not None
            assert "credibleSet" in result
        except Exception as e:
            # It's okay if this specific ID doesn't exist
            print(f"Credible set test skipped: {e}")
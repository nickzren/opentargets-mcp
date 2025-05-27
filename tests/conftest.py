# tests/conftest.py
import pytest
import asyncio
from opentargets_mcp.queries import OpenTargetsClient

# Common test identifiers that can be used across different test files
TEST_TARGET_ID_BRAF = "ENSG00000157764"      # BRAF
TEST_TARGET_ID_EGFR = "ENSG00000146648"      # EGFR
TEST_DISEASE_ID_ASTHMA = "EFO_0000270"       # Asthma
TEST_DISEASE_ID_MELANOMA = "EFO_0000583"     # Melanoma
TEST_DRUG_ID_VEMURAFENIB = "CHEMBL1201583"   # Vemurafenib
TEST_DRUG_ID_OSIMERTINIB = "CHEMBL3308093"   # Osimertinib
TEST_VARIANT_ID_1 = "1_154453788_C_T"
TEST_VARIANT_ID_RS699 = "rs699"             # Example rsID variant
TEST_STUDY_ID = "GCST90002357"       # Example GWAS study
TEST_STUDY_LOCUS_ID = "GCST004131_1_109817651" # Example credible set

@pytest.fixture(scope="function")
async def client():
    """
    Provides an OpenTargetsClient instance for each test function.
    Ensures the client session is created in the correct event loop and closed afterwards.
    """
    ot_client = OpenTargetsClient()
    # Ensure the client has an active session before yielding
    # This can be important if _ensure_session is not called by the first operation in a test
    await ot_client._ensure_session()
    yield ot_client
    # Ensure client session is closed after each test
    await ot_client.close()
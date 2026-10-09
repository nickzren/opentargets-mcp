"""Live checks for name resolution against the current Open Targets release."""

import pytest

from opentargets_mcp.exceptions import ValidationError
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.resolver import resolve_param
from opentargets_mcp.tools.study import StudyApi
from opentargets_mcp.tools.variant import VariantApi


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name, term, expected",
    [
        ("chembl_id", "pembrolizumab", "CHEMBL3137343"),
        ("chembl_id", "metformin", "CHEMBL1431"),
        ("efo_id", "breast cancer", "MONDO_0007254"),
        ("ensembl_id", "insulin", "ENSG00000254647"),
        ("variant_id", "rs4129267", "1_154453788_C_T"),
        ("variant_id", "chr1:154453788:C:T", "1_154453788_C_T"),
    ],
)
async def test_names_resolve_to_the_exact_match(
    client: OpenTargetsClient, name, term, expected
):
    assert await resolve_param(client, name, term) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name, term, listed",
    [
        ("ensembl_id", "PD-1", "ENSG00000188389 (PDCD1)"),
        ("chembl_id", "gleevec", "CHEMBL941 (IMATINIB)"),
        ("variant_id", "rs1042522", "17_7676154_G_C"),
    ],
)
async def test_ambiguous_names_raise_with_candidates(
    client: OpenTargetsClient, name, term, listed
):
    with pytest.raises(ValidationError, match=f"Ambiguous {name} '{term}'") as exc_info:
        await resolve_param(client, name, term)
    assert listed in str(exc_info.value)


@pytest.mark.asyncio
async def test_variant_info_accepts_rsid(client: OpenTargetsClient):
    variant_id = await resolve_param(client, "variant_id", "rs4129267")
    result = await VariantApi().get_variant_info(client, variant_id)
    assert result["variant"]["id"] == "1_154453788_C_T"


@pytest.mark.asyncio
async def test_credible_sets_accept_rsids(client: OpenTargetsClient):
    variant_ids = await resolve_param(client, "variant_ids", ["rs4129267"])
    result = await StudyApi().get_credible_sets(client, variant_ids=variant_ids, page_size=1)
    assert result["credibleSets"]["count"] > 0

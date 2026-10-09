"""Name resolution must not silently pick among tied mapIds hits.

Live mapIds scores every hit 1, so the old max-by-score rule took upstream's
first hit: 'pembrolizumab' became NIVOLUMAB, 'metformin' ROSIGLITAZONE and
'rs1042522' an arbitrary allele. Payloads mirror live 26.09 mapIds responses.
"""

import pytest
from fastmcp import Client

import opentargets_mcp.server as server_module
from opentargets_mcp.exceptions import ValidationError
from opentargets_mcp.resolver import _best_hit, resolve_param


def _hit(id_, name, **obj):
    return {"id": id_, "name": name, "score": 1, "object": obj or None}


MAP_IDS_HITS = {
    "pembrolizumab": [
        _hit("CHEMBL2108738", "NIVOLUMAB"),
        _hit("CHEMBL4297843", "TORIPALIMAB"),
        _hit("CHEMBL3137343", "PEMBROLIZUMAB"),
    ],
    "gleevec": [
        _hit("CHEMBL1642", "IMATINIB MESYLATE"),
        _hit("CHEMBL941", "IMATINIB"),
    ],
    "insulin": [
        _hit("ENSG00000129965", "INS-IGF2", approvedSymbol="INS-IGF2", approvedName="INS-IGF2 readthrough"),
        _hit("ENSG00000254647", "INS", approvedSymbol="INS", approvedName="insulin"),
    ],
    "PD-1": [
        _hit("ENSG00000215472", "RPL17-C18orf32", approvedSymbol="RPL17-C18orf32"),
        _hit("ENSG00000188389", "PDCD1", approvedSymbol="PDCD1", approvedName="programmed cell death 1"),
        _hit("ENSG00000265681", "RPL17", approvedSymbol="RPL17"),
    ],
    "insulin products": [
        _hit(f"CHEMBL{index}", f"INSULIN {index}") for index in range(9)
    ],
    "breast cancer": [
        _hit("MONDO_0004989", "breast carcinoma"),
        _hit("MONDO_0007254", "breast cancer"),
    ],
    "Breast  Cancer": [
        _hit("MONDO_0004989", "breast carcinoma"),
        _hit("MONDO_0007254", "breast cancer"),
    ],
    "p53": [
        _hit("ENSG00000141510", "TP53", approvedSymbol="TP53"),
        _hit("ENSG00000141510", "TP53", approvedSymbol="TP53"),
    ],
    "rs4129267": [_hit("1_154453788_C_T", "1_154453788_C_T")],
    "RS4129267": [_hit("1_154453788_C_T", "1_154453788_C_T")],
    "1_154453788_c_t": [_hit("1_154453788_C_T", "1_154453788_C_T")],
    "rs1042522": [
        _hit("17_7676154_G_A", "17_7676154_G_A"),
        _hit("17_7676154_G_T", "17_7676154_G_T"),
        _hit("17_7676154_G_C", "17_7676154_G_C"),
    ],
    "asthma GWAS": [_hit("GCST90002357", "GCST90002357")],
}


class _MapIdsClient:
    """Answers mapIds from MAP_IDS_HITS and records every query."""

    def __init__(self):
        self.queries = []

    async def _query(self, query, variables=None):
        self.queries.append((query, variables))
        if "mapIds" not in query:
            return {"credibleSets": {"count": 0, "rows": []}}
        return {
            "mapIds": {
                "mappings": [
                    {"term": term, "hits": MAP_IDS_HITS.get(term, [])}
                    for term in variables["queryTerms"]
                ]
            }
        }

    @property
    def mapped_terms(self):
        return [
            variables["queryTerms"]
            for query, variables in self.queries
            if "mapIds" in query
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name, term, expected",
    [
        ("chembl_id", "pembrolizumab", "CHEMBL3137343"),
        ("ensembl_id", "insulin", "ENSG00000254647"),
        ("efo_id", "breast cancer", "MONDO_0007254"),
        ("efo_id", "Breast  Cancer", "MONDO_0007254"),
        ("ensembl_id", "p53", "ENSG00000141510"),
        ("variant_id", "rs4129267", "1_154453788_C_T"),
    ],
)
async def test_tied_hits_resolve_to_the_exact_match(name, term, expected):
    assert await resolve_param(_MapIdsClient(), name, term) == expected


@pytest.mark.asyncio
async def test_tie_without_exact_match_raises_with_candidates():
    with pytest.raises(ValidationError) as exc_info:
        await resolve_param(_MapIdsClient(), "chembl_id", "gleevec")

    assert str(exc_info.value) == (
        "Ambiguous chembl_id 'gleevec': CHEMBL1642 (IMATINIB MESYLATE), "
        "CHEMBL941 (IMATINIB); pass an ID"
    )


@pytest.mark.asyncio
async def test_ambiguity_error_lists_pdcd1_for_pd1():
    with pytest.raises(ValidationError, match=r"ENSG00000188389 \(PDCD1\)"):
        await resolve_param(_MapIdsClient(), "ensembl_id", "PD-1")


@pytest.mark.asyncio
async def test_ambiguity_error_caps_candidates_at_five():
    with pytest.raises(ValidationError) as exc_info:
        await resolve_param(_MapIdsClient(), "chembl_id", "insulin products")

    message = str(exc_info.value)
    assert "CHEMBL4 (INSULIN 4)" in message
    assert "CHEMBL5" not in message
    assert message.endswith("(+4 more); pass an ID")


@pytest.mark.asyncio
async def test_multi_allelic_rsid_raises_listing_alleles():
    with pytest.raises(ValidationError) as exc_info:
        await resolve_param(_MapIdsClient(), "variant_id", "rs1042522")

    assert str(exc_info.value) == (
        "Ambiguous variant_id 'rs1042522': 17_7676154_G_A, 17_7676154_G_T, "
        "17_7676154_G_C; pass an ID"
    )


@pytest.mark.asyncio
async def test_list_params_resolve_names_and_keep_ids():
    client = _MapIdsClient()

    variant_ids = await resolve_param(
        client, "variant_ids", ["rs4129267", "X_67545785_G_A"]
    )
    study_ids = await resolve_param(client, "study_ids", ["asthma GWAS", "GCST004131"])

    assert variant_ids == ["1_154453788_C_T", "X_67545785_G_A"]
    assert study_ids == ["GCST90002357", "GCST004131"]
    assert client.mapped_terms == [["rs4129267"], ["asthma GWAS"]]


@pytest.mark.asyncio
async def test_list_params_raise_on_an_ambiguous_member():
    with pytest.raises(ValidationError, match="Ambiguous variant_ids 'rs1042522'"):
        await resolve_param(
            _MapIdsClient(), "variant_ids", ["rs4129267", "rs1042522"]
        )


@pytest.mark.asyncio
async def test_surrounding_whitespace_is_stripped():
    client = _MapIdsClient()

    assert await resolve_param(client, "ensembl_id", " ENSG00000157764 ") == "ENSG00000157764"
    assert await resolve_param(client, "chembl_id", " pembrolizumab\t") == "CHEMBL3137343"
    assert client.mapped_terms == [["pembrolizumab"]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value, expected",
    [
        ("1_154453788_C_T", "1_154453788_C_T"),
        ("X_67545785_G_A", "X_67545785_G_A"),
        ("MT_12017_A_G", "MT_12017_A_G"),
        ("Y_634734_C_G", "Y_634734_C_G"),
        ("X_55115286_A_AC", "X_55115286_A_AC"),
        (
            "OTVAR_20_7977116_061a7484fe8a1f88a686611e2ca7fd5a",
            "OTVAR_20_7977116_061a7484fe8a1f88a686611e2ca7fd5a",
        ),
        ("chr1:154453788:C:T", "1_154453788_C_T"),
        ("1:154453788:C:T", "1_154453788_C_T"),
        ("chr1_154453788_C_T", "1_154453788_C_T"),
        ("chrX:67545785:G:A", "X_67545785_G_A"),
    ],
)
async def test_canonical_variant_ids_skip_the_network(value, expected):
    client = _MapIdsClient()

    assert await resolve_param(client, "variant_id", value) == expected
    assert client.queries == []


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["rs4129267", "RS4129267", "1_154453788_c_t"])
async def test_noncanonical_variant_ids_go_through_map_ids(value):
    client = _MapIdsClient()

    assert await resolve_param(client, "variant_id", value) == "1_154453788_C_T"
    assert client.mapped_terms == [[value]]


def test_best_hit_returns_none_when_ambiguous():
    assert _best_hit({"term": "gleevec", "hits": MAP_IDS_HITS["gleevec"]}) is None
    assert _best_hit({"term": "IMATINIB", "hits": MAP_IDS_HITS["gleevec"]})["id"] == "CHEMBL941"


@pytest.mark.asyncio
async def test_ambiguity_reaches_the_mcp_caller(monkeypatch):
    monkeypatch.setattr(server_module, "get_client", _MapIdsClient)

    async with Client(server_module.mcp) as mcp_client:
        result = await mcp_client.call_tool(
            "get_drug_info", {"chembl_id": "gleevec"}, raise_on_error=False
        )

    assert result.is_error
    text = " ".join(block.text for block in result.content if getattr(block, "text", None))
    assert "Ambiguous chembl_id 'gleevec'" in text


@pytest.mark.asyncio
async def test_credible_sets_resolve_variant_ids(monkeypatch):
    client = _MapIdsClient()
    monkeypatch.setattr(server_module, "get_client", lambda: client)

    async with Client(server_module.mcp) as mcp_client:
        await mcp_client.call_tool("get_credible_sets", {"variant_ids": ["rs4129267"]})

    _query, variables = client.queries[-1]
    assert variables["variantIds"] == ["1_154453788_C_T"]

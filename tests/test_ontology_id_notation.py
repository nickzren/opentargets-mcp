"""Colon-form ontology identifiers must resolve like underscore form.

Open Targets 26.06 search accepts `MONDO:0004979`, but `mapIds` — which the
resolver uses — returns no hits for it, so colon input raised ValidationError
while the equivalent underscore input worked.
"""

import pytest

from opentargets_mcp.resolver import resolve_param, resolve_params


class _NoQueryClient:
    """Fails loudly if resolution falls through to the network."""

    async def _query(self, *_args, **_kwargs):  # pragma: no cover - must not run
        raise AssertionError("a recognized identifier should not need resolving")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value, expected",
    [
        ("MONDO:0004979", "MONDO_0004979"),
        ("EFO:0000270", "EFO_0000270"),
        ("HP:0001250", "HP_0001250"),
        ("DOID:9352", "DOID_9352"),
        ("Orphanet:558", "Orphanet_558"),
        ("OTAR:0000018", "OTAR_0000018"),
        ("mondo:0004979", "MONDO_0004979"),
        ("MONDO_0004979", "MONDO_0004979"),
    ],
)
async def test_colon_form_disease_ids_are_accepted(value, expected):
    assert await resolve_param(_NoQueryClient(), "efo_id", value) == expected


@pytest.mark.asyncio
async def test_colon_and_underscore_forms_agree():
    colon = await resolve_param(_NoQueryClient(), "efo_id", "MONDO:0004979")
    underscore = await resolve_param(_NoQueryClient(), "efo_id", "MONDO_0004979")
    assert colon == underscore


@pytest.mark.asyncio
async def test_batches_normalize_each_term():
    result = await resolve_param(
        _NoQueryClient(), "efo_ids", ["MONDO:0004979", "MONDO_0005105"]
    )
    assert result == ["MONDO_0004979", "MONDO_0005105"]


@pytest.mark.asyncio
async def test_resolve_params_normalizes_disease_batches():
    resolved = await resolve_params(
        _NoQueryClient(), {"disease_ids": ["MONDO:0004979"], "size": 5}
    )
    assert resolved == {"disease_ids": ["MONDO_0004979"], "size": 5}


@pytest.mark.asyncio
async def test_variant_colon_notation_is_left_alone():
    """Variant IDs use colons legitimately; normalization must not touch them."""
    value = "chr1:154453788:C:T"
    assert await resolve_param(_NoQueryClient(), "variant_id", value) == value


@pytest.mark.asyncio
async def test_unknown_prefix_is_not_rewritten():
    """An unrecognized prefix must still go through normal resolution."""
    captured = {}

    class _RecordingClient:
        async def _query(self, _query, variables=None):
            captured.update(variables or {})
            return {
                "mapIds": {
                    "mappings": [
                        {
                            "term": "NOTANONTOLOGY:123",
                            "hits": [{"id": "MONDO_9999999", "score": 1.0}],
                        }
                    ]
                }
            }

    result = await resolve_param(_RecordingClient(), "efo_id", "NOTANONTOLOGY:123")
    assert captured["queryTerms"] == ["NOTANONTOLOGY:123"]
    assert result == "MONDO_9999999"

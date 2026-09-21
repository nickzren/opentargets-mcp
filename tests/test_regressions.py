import pathlib
import re

import aiohttp
from fastmcp.exceptions import ToolError
import pytest

from opentargets_mcp.exceptions import UpstreamQueryError, ValidationError
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.settings import ServerSettings
from opentargets_mcp.resolver import _best_hit, _best_hit_id
from opentargets_mcp.tools.evidence import EvidenceApi
from opentargets_mcp.tools.graphql import GraphqlApi
from opentargets_mcp.tools.search import SearchApi
from opentargets_mcp.tools.study import StudyApi
from opentargets_mcp.tools.target import TargetApi
from opentargets_mcp.tools.variant import VariantApi
import opentargets_mcp.tools.graphql as graphql_module
from opentargets_mcp.utils import (
    flatten_mechanism_targets,
    page_list,
    promote_clinical_candidates,
    validate_required_int,
)


class _FakeResponse:
    def __init__(
        self, status: int, body: str, url: str = "https://example.test/graphql"
    ):
        self.status = status
        self._body = body
        self.url = url

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    async def text(self) -> str:
        return self._body

    def raise_for_status(self) -> None:
        if self.ok:
            return
        raise aiohttp.ClientResponseError(
            request_info=None,
            history=(),
            status=self.status,
            message=self._body,
            headers=None,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]):
        self._responses = responses
        self.closed = False
        self.calls = 0

    def post(self, *_args, **_kwargs):
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_search_entities_handles_empty_hits_without_crashing(monkeypatch):
    api = SearchApi()

    async def fake_search_direct(
        client, query_string, entity_names, page_index, page_size
    ):
        if query_string == "alias":
            return {"search": {"total": 0, "hits": []}}
        return {
            "search": {
                "total": 1,
                "hits": [{"id": "ENSG_TEST", "entity": "target", "name": "TEST"}],
            }
        }

    async def fake_map_ids(client, query_terms, entity_names=None):
        return {
            "mapIds": {
                "mappings": [
                    {
                        "term": query_terms[0],
                        "hits": [{"id": "ENSG_TEST", "name": "TEST", "score": 1.0}],
                    }
                ]
            }
        }

    monkeypatch.setattr(api, "_search_direct", fake_search_direct)
    monkeypatch.setattr(api.meta_api, "map_ids", fake_map_ids)

    result = await api.search_entities(object(), "alias", entity_names=["target"])
    assert result["search"]["hits"][0]["id"] == "ENSG_TEST"
    assert result["search"]["triples"] == [
        {"id": "ENSG_TEST", "entity": "target", "name": "TEST"}
    ]


@pytest.mark.asyncio
async def test_query_cache_returns_defensive_copy():
    client = OpenTargetsClient(cache_ttl=3600, cache_max_entries=8)
    client.session = _FakeSession(
        [
            _FakeResponse(
                status=200,
                body='{"data":{"target":{"literatureOcurrences":{"rows":[1,2,3,4,5]}}}}',
            )
        ]
    )

    first = await client._query("query CachedResult { target { id } }")
    first["target"]["literatureOcurrences"]["rows"] = [1]

    second = await client._query("query CachedResult { target { id } }")
    assert second["target"]["literatureOcurrences"]["rows"] == [1, 2, 3, 4, 5]
    assert client.session.calls == 1


def test_query_cache_max_entries_enforced():
    client = OpenTargetsClient(cache_ttl=3600, cache_max_entries=2)
    client._set_cached("a", {"value": 1})
    client._set_cached("b", {"value": 2})
    client._set_cached("c", {"value": 3})

    assert len(client._cache) == 2
    assert "a" not in client._cache
    assert "b" in client._cache
    assert "c" in client._cache


def test_client_rejects_zero_retries():
    with pytest.raises(ValueError):
        OpenTargetsClient(max_retries=0)


@pytest.mark.asyncio
async def test_graphql_query_retries_transient_http_errors():
    api = GraphqlApi()
    client = OpenTargetsClient(max_retries=2, retry_delay=0)
    client.session = _FakeSession(
        [
            _FakeResponse(status=500, body='{"errors":[{"message":"temporary"}]}'),
            _FakeResponse(status=200, body='{"data":{"meta":{"name":"ok"}}}'),
        ]
    )

    result = await api.graphql_query(
        client, query_string="query Meta { meta { name } }"
    )
    assert result["status"] == "success"
    assert result["result"]["meta"]["name"] == "ok"
    assert client.session.calls == 2


@pytest.mark.asyncio
async def test_graphql_query_returns_error_envelope_for_http_400():
    api = GraphqlApi()
    client = OpenTargetsClient(max_retries=1, retry_delay=0)
    client.session = _FakeSession(
        [_FakeResponse(status=400, body='{"errors":[{"message":"Bad query"}]}')]
    )

    result = await api.graphql_query(client, query_string="query { badField }")
    assert result["status"] == "error"
    assert result["result"] is None
    assert result["message"][0]["message"] == "Bad query"


@pytest.mark.asyncio
async def test_graphql_query_returns_error_envelope_for_non_json_response():
    api = GraphqlApi()
    client = OpenTargetsClient(max_retries=1, retry_delay=0)
    client.session = _FakeSession([_FakeResponse(status=200, body="<html>bad</html>")])

    result = await api.graphql_query(client, query_string="query { meta { name } }")

    assert result == {
        "status": "error",
        "result": None,
        "message": [{"message": "Non-JSON response from GraphQL endpoint"}],
    }


@pytest.mark.asyncio
async def test_query_raises_when_graphql_errors_are_present():
    """Curated tools must fail loudly; partial data stays a raw-tool concern."""
    client = OpenTargetsClient(max_retries=1, retry_delay=0)
    client.session = _FakeSession(
        [
            _FakeResponse(
                status=200,
                body='{"data":{"target":null},"errors":[{"message":"missing"}]}',
            )
        ]
    )

    with pytest.raises(UpstreamQueryError) as exc_info:
        await client._query("query PartialData { target { id } }")

    assert "missing" in str(exc_info.value)


@pytest.mark.asyncio
async def test_query_raises_upstream_error_with_status_on_non_ok_response():
    client = OpenTargetsClient(max_retries=1, retry_delay=0)
    client.session = _FakeSession(
        [_FakeResponse(status=400, body='{"errors":[{"message":"Bad query"}]}')]
    )

    with pytest.raises(UpstreamQueryError) as exc_info:
        await client._query("query BadField { badField }")

    assert "Bad query" in str(exc_info.value)
    assert exc_info.value.status == 400
    assert isinstance(exc_info.value.__cause__, aiohttp.ClientResponseError)


@pytest.mark.asyncio
async def test_graphql_batch_query_enforces_batch_limits():
    api = GraphqlApi()
    with pytest.raises(
        ValidationError,
        match=f"variables_list cannot exceed {graphql_module.MAX_GRAPHQL_BATCH_ITEMS} items.",
    ):
        await api.graphql_batch_query(
            client=object(),  # type: ignore[arg-type]
            query_string="query { meta { name } }",
            variables_list=[{}] * (graphql_module.MAX_GRAPHQL_BATCH_ITEMS + 1),
        )


@pytest.mark.asyncio
async def test_graphql_batch_query_enforces_concurrency_limit():
    api = GraphqlApi()
    with pytest.raises(
        ValidationError,
        match=f"max_concurrency must be <= {graphql_module.MAX_GRAPHQL_BATCH_CONCURRENCY}.",
    ):
        await api.graphql_batch_query(
            client=object(),  # type: ignore[arg-type]
            query_string="query { meta { name } }",
            variables_list=[{}],
            max_concurrency=graphql_module.MAX_GRAPHQL_BATCH_CONCURRENCY + 1,
        )


@pytest.mark.asyncio
async def test_graphql_query_blocks_comment_prefixed_mutation():
    api = GraphqlApi()
    client = OpenTargetsClient()

    try:
        with pytest.raises(ValidationError):
            await api.graphql_query(
                client, query_string="#comment\nmutation { fakeMutation }"
            )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_graphql_schema_cache_is_scoped_by_base_url(monkeypatch):
    graphql_module._schema_cache.clear()

    monkeypatch.setattr(
        graphql_module, "build_client_schema", lambda introspection: introspection
    )
    monkeypatch.setattr(
        graphql_module, "print_schema", lambda schema: schema["schema_text"]
    )

    class _FakeClient:
        def __init__(self, base_url: str, schema_text: str):
            self.base_url = base_url
            self.schema_text = schema_text

        async def _query(self, _query_string):
            return {"schema_text": self.schema_text}

    api = GraphqlApi()
    schema_a = await api.graphql_schema(
        _FakeClient("https://api.one/graphql", "schema one")
    )
    schema_b = await api.graphql_schema(
        _FakeClient("https://api.two/graphql", "schema two")
    )

    assert schema_a == "schema one"
    assert schema_b == "schema two"


def test_server_settings_uses_environment_aliases(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("FASTMCP_SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("FASTMCP_SERVER_PORT", "8123")
    monkeypatch.setenv("OPEN_TARGETS_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("OPEN_TARGETS_RATE_LIMIT_RPS", "5.5")
    monkeypatch.setenv("OPEN_TARGETS_RATE_LIMIT_BURST", "40")

    settings = ServerSettings()
    assert settings.mcp_transport == "http"
    assert settings.fastmcp_server_host == "127.0.0.1"
    assert settings.fastmcp_server_port == 8123
    assert settings.open_targets_rate_limit_enabled is True
    assert settings.open_targets_rate_limit_rps == 5.5
    assert settings.open_targets_rate_limit_burst == 40


@pytest.mark.asyncio
async def test_tool_wrapper_rejects_page_size_above_global_max(monkeypatch):
    import opentargets_mcp.server as server_module

    async def fake_tool(_client, page_size: int):
        return {"page_size": page_size}

    monkeypatch.setattr(server_module, "get_client", lambda: object())

    wrapper = server_module._make_tool_wrapper(fake_tool)
    # The wrapper is the MCP boundary: bad input surfaces as ToolError so the
    # message survives mask_error_details, with the ValidationError as cause.
    with pytest.raises(
        ToolError,
        match=f"page_size must be <= {server_module.MAX_PAGE_SIZE}.",
    ) as exc_info:
        await wrapper(page_size=server_module.MAX_PAGE_SIZE + 1)
    assert isinstance(exc_info.value.__cause__, ValidationError)


def test_server_main_rejects_port_above_tcp_max(monkeypatch):
    import opentargets_mcp.server as server_module

    monkeypatch.setattr("sys.argv", ["opentargets-mcp", "--port", "65536"])
    with pytest.raises(SystemExit) as exc:
        server_module.main()
    assert exc.value.code == 2


def test_server_main_lists_tools_with_v3_shape(monkeypatch, capsys):
    import opentargets_mcp.server as server_module

    class _Tool:
        def __init__(self, name: str, description: str | None):
            self.name = name
            self.description = description

    async def fake_list_tools():
        return [
            _Tool("zeta_tool", "Zeta summary\nExtra details"),
            _Tool("alpha_tool", None),
        ]

    monkeypatch.setattr(server_module.mcp, "list_tools", fake_list_tools)
    monkeypatch.setattr("sys.argv", ["opentargets-mcp", "--list-tools"])

    server_module.main()

    assert capsys.readouterr().out.strip().splitlines() == [
        "alpha_tool: No description available",
        "zeta_tool: Zeta summary",
    ]


def test_server_main_lists_tools_with_dict_shape(monkeypatch, capsys):
    import opentargets_mcp.server as server_module

    class _Tool:
        def __init__(self, name: str, description: str | None):
            self.name = name
            self.description = description

    async def fake_list_tools():
        return {
            "zeta_tool": _Tool("zeta_tool", "Zeta summary\nExtra details"),
            "alpha_tool": _Tool("alpha_tool", None),
        }

    monkeypatch.setattr(server_module.mcp, "list_tools", fake_list_tools)
    monkeypatch.setattr("sys.argv", ["opentargets-mcp", "--list-tools"])

    server_module.main()

    assert capsys.readouterr().out.strip().splitlines() == [
        "alpha_tool: No description available",
        "zeta_tool: Zeta summary",
    ]


@pytest.mark.asyncio
async def test_tool_wrapper_rejects_bool_page_size(monkeypatch):
    import opentargets_mcp.server as server_module

    async def fake_tool(_client, page_size: int):
        return {"page_size": page_size}

    monkeypatch.setattr(server_module, "get_client", lambda: object())

    wrapper = server_module._make_tool_wrapper(fake_tool)
    with pytest.raises(
        ToolError, match="page_size must be an integer >= 1."
    ) as exc_info:
        await wrapper(page_size=True)
    assert isinstance(exc_info.value.__cause__, ValidationError)


def test_validate_required_int_rejects_bool():
    with pytest.raises(ValidationError, match="size must be an integer >= 1."):
        validate_required_int(True, "size")


def test_promote_clinical_candidates_preserves_legacy_known_drugs_shape():
    parent = {
        "drugAndClinicalCandidates": {
            "count": 2,
            "rows": [
                {
                    "maxClinicalStage": "PHASE_3",
                    "drug": {"id": "CHEMBL_A", "maximumClinicalStage": "APPROVAL"},
                    "clinicalReports": [
                        {
                            "id": "NCT1",
                            "source": "clinicaltrials",
                            "trialOverallStatus": "Completed",
                            "url": "https://example.test/NCT1",
                        }
                    ],
                    "diseases": [{"disease": {"id": "EFO_1", "name": "Disease"}}],
                },
                {"drug": {"id": "CHEMBL_B"}},
            ],
        }
    }

    promote_clinical_candidates(parent, page_size=1)

    assert "drugAndClinicalCandidates" not in parent
    known_drugs = parent["knownDrugs"]
    # count is the upstream total, not the page length.
    assert known_drugs["count"] == 2
    assert len(known_drugs["rows"]) == 1
    row = known_drugs["rows"][0]
    assert row["phase"] == 3
    assert row["status"] == "Completed"
    assert row["urls"] == [
        {"name": "NCT1", "url": "https://example.test/NCT1"}
    ]
    assert row["disease"]["id"] == "EFO_1"
    assert row["drug"]["isApproved"] is True


def test_subcellular_locations_query_selects_target_modifier():
    """Without targetModifier, isoform-specific locations read as whole-protein."""
    source = pathlib.Path(
        "src/opentargets_mcp/tools/target/biology.py"
    ).read_text()
    body = source.split("query TargetSubcellularLocations", 1)[1].split('"""', 1)[0]
    assert "targetModifier" in body


def test_page_list_preserves_client_side_slice_behavior():
    assert page_list(["a", "b", "c", "d"], page_index=1, page_size=2) == [
        "c",
        "d",
    ]
    assert page_list({"not": "a list"}, page_index=1, page_size=2) == {
        "not": "a list"
    }


def test_best_hit_helper_preserves_full_hit_and_id_access():
    mapping = {
        "hits": [
            {"id": "LOW", "name": "Low", "score": 0.2},
            {"id": "HIGH", "name": "High", "score": 0.9},
        ]
    }

    assert _best_hit(mapping) == {"id": "HIGH", "name": "High", "score": 0.9}
    assert _best_hit_id(mapping) == "HIGH"


def test_flatten_mechanism_targets_deduplicates_and_copies_optional_fields():
    rows = [
        {
            "mechanismOfAction": "inhibits",
            "actionType": "INHIBITOR",
            "targets": [
                {"id": "ENSG1", "approvedSymbol": "A"},
                {"id": "ENSG2", "approvedSymbol": "B"},
            ],
        },
        {
            "mechanismOfAction": "binds",
            "actionType": "BINDER",
            "targets": [{"id": "ENSG1", "approvedSymbol": "A2"}],
        },
    ]

    targets = flatten_mechanism_targets(rows, copy_mechanism_fields=True)

    assert [target["id"] for target in targets] == ["ENSG1", "ENSG2"]
    assert targets[0]["approvedSymbol"] == "A"
    assert targets[0]["mechanismOfAction"] == "inhibits"
    assert targets[0]["actionType"] == "INHIBITOR"


@pytest.mark.asyncio
async def test_get_similar_targets_rejects_invalid_size():
    api = SearchApi()
    with pytest.raises(ValidationError, match="size must be an integer >= 1."):
        await api.get_similar_targets(
            object(),  # type: ignore[arg-type]
            "ENSG00000157764",
            size=True,
        )


@pytest.mark.asyncio
async def test_get_similar_targets_rejects_invalid_threshold():
    api = SearchApi()
    with pytest.raises(
        ValidationError, match="threshold must be between 0 and 1 when provided."
    ):
        await api.get_similar_targets(
            object(),  # type: ignore[arg-type]
            "ENSG00000157764",
            threshold=1.5,
        )


@pytest.mark.asyncio
async def test_variant_evidences_rejects_none_size():
    api = VariantApi()
    client = OpenTargetsClient()
    try:
        with pytest.raises(ValidationError):
            await api.get_variant_evidences(client, "1_154453788_C_T", size=None)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_target_disease_evidence_rejects_none_size():
    api = EvidenceApi()
    client = OpenTargetsClient()
    try:
        with pytest.raises(ValidationError):
            await api.get_target_disease_evidence(
                client,
                "ENSG00000157764",
                "EFO_0003884",
                size=None,
            )
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_target_disease_evidence_supports_fields_projection():
    class _FakeClient:
        async def _query(self, *_args, **_kwargs):
            return {
                "target": {
                    "evidences": {
                        "count": 1,
                        "rows": [{"id": "ev1", "score": 0.7, "datasourceId": "eva"}],
                    }
                }
            }

    api = EvidenceApi()
    result = await api.get_target_disease_evidence(
        _FakeClient(),
        "ENSG00000157764",
        "EFO_0003884",
        fields=["target.evidences.rows.id"],
    )
    assert result == {"target": {"evidences": {"rows": [{"id": "ev1"}]}}}


@pytest.mark.asyncio
async def test_target_disease_biomarkers_returns_only_biomarker_rows():
    class _FakeClient:
        async def _query(self, *_args, **_kwargs):
            return {
                "target": {
                    "evidences": {
                        "count": 3,
                        "rows": [
                            {"id": "1", "biomarkerName": "PD-L1"},
                            {"id": "2", "biomarkers": {"geneExpression": []}},
                            {"id": "3", "biomarkerName": None, "biomarkers": None},
                        ],
                    }
                }
            }

    api = EvidenceApi()
    result = await api.get_target_disease_biomarkers(
        _FakeClient(),
        "ENSG00000157764",
        "EFO_0003884",
    )
    rows = result["target"]["evidences"]["rows"]
    assert [row["id"] for row in rows] == ["1", "2"]
    assert result["target"]["evidences"]["count"] == 2
    assert result["target"]["evidences"]["unfilteredCount"] == 3
    assert result["target"]["evidences"]["filteredCount"] == 2


@pytest.mark.asyncio
async def test_variant_evidences_supports_fields_projection():
    class _FakeClient:
        async def _query(self, *_args, **_kwargs):
            return {
                "variant": {
                    "evidences": {
                        "count": 1,
                        "rows": [{"id": "v1", "datasourceId": "eva"}],
                    }
                }
            }

    api = VariantApi()
    result = await api.get_variant_evidences(
        _FakeClient(),
        "1_154453788_C_T",
        fields=["variant.evidences.rows.id"],
    )
    assert result == {"variant": {"evidences": {"rows": [{"id": "v1"}]}}}


@pytest.mark.asyncio
async def test_studies_by_disease_supports_fields_projection():
    class _FakeClient:
        async def _query(self, *_args, **_kwargs):
            return {
                "studies": {
                    "count": 1,
                    "rows": [{"id": "GCST0001", "traitFromSource": "Trait"}],
                }
            }

    api = StudyApi()
    result = await api.get_studies_by_disease(
        _FakeClient(),
        ["EFO_0003884"],
        fields=["studies.rows.id"],
    )
    assert result == {"studies": {"rows": [{"id": "GCST0001"}]}}


@pytest.mark.asyncio
async def test_target_expression_keeps_fields_as_third_positional_argument():
    """Pagination must not shift `fields` out of its published position."""
    captured = {}

    class _FakeClient:
        async def _query(self, _query, variables=None):
            captured.update(variables or {})
            return {
                "target": {
                    "id": "ENSG00000157764",
                    "baselineExpression": {"count": 1, "rows": [{"median": 1.0}]},
                }
            }

    api = TargetApi()
    result = await api.get_target_expression(
        _FakeClient(), "ENSG00000157764", ["target.id"]
    )

    assert captured["pageIndex"] == 0
    assert result == {"target": {"id": "ENSG00000157764"}}


@pytest.mark.asyncio
async def test_target_expression_supports_fields_projection():
    class _FakeClient:
        async def _query(self, *_args, **_kwargs):
            return {
                "target": {
                    "id": "ENSG00000157764",
                    "baselineExpression": {
                        "count": 1,
                        "rows": [
                            {
                                "tissueBiosample": {"biosampleName": "liver"},
                                "median": 12.5,
                            }
                        ],
                    },
                }
            }

    api = TargetApi()
    result = await api.get_target_expression(
        _FakeClient(),
        "ENSG00000157764",
        fields=["target.baselineExpression.rows.tissueBiosample.biosampleName"],
    )
    assert result == {
        "target": {
            "baselineExpression": {
                "rows": [
                    {
                        "tissueBiosample": {
                            "biosampleName": "liver",
                        }
                    }
                ]
            }
        }
    }


@pytest.mark.asyncio
async def test_target_interactions_supports_fields_projection():
    class _FakeClient:
        async def _query(self, *_args, **_kwargs):
            return {
                "target": {
                    "interactions": {
                        "count": 1,
                        "rows": [{"score": 0.9, "targetB": {"approvedSymbol": "EGFR"}}],
                    }
                }
            }

    api = TargetApi()
    result = await api.get_target_interactions(
        _FakeClient(),
        "ENSG00000157764",
        fields=["target.interactions.rows.targetB.approvedSymbol"],
    )
    assert result == {
        "target": {
            "interactions": {
                "rows": [{"targetB": {"approvedSymbol": "EGFR"}}],
            }
        }
    }


@pytest.mark.asyncio
async def test_study_credible_sets_supports_fields_projection():
    class _FakeClient:
        async def _query(self, *_args, **_kwargs):
            return {
                "study": {
                    "credibleSets": {
                        "count": 1,
                        "rows": [{"studyLocusId": "SL1", "studyId": "GCST001"}],
                    }
                }
            }

    api = StudyApi()
    result = await api.get_study_credible_sets(
        _FakeClient(),
        "GCST001",
        fields=["study.credibleSets.rows.studyLocusId"],
    )
    assert result == {
        "study": {
            "credibleSets": {
                "rows": [{"studyLocusId": "SL1"}],
            }
        }
    }


@pytest.mark.asyncio
async def test_credible_sets_supports_fields_projection():
    class _FakeClient:
        async def _query(self, *_args, **_kwargs):
            return {
                "credibleSets": {
                    "count": 1,
                    "rows": [{"studyLocusId": "SL1", "studyId": "GCST001"}],
                }
            }

    api = StudyApi()
    result = await api.get_credible_sets(
        _FakeClient(),
        fields=["credibleSets.rows.studyId"],
    )
    assert result == {"credibleSets": {"rows": [{"studyId": "GCST001"}]}}


def test_extract_tool_description_returns_only_summary_line():
    from opentargets_mcp.server import _extract_tool_description

    api = TargetApi()
    summary = _extract_tool_description(api.get_target_info)
    assert summary == "Retrieve core identity details for a target gene."

    long_doc = (api.get_target_info.__doc__ or "").strip()
    assert "**When to use**" in long_doc
    assert summary is not None
    assert "**When to use**" not in summary


def test_extract_tool_description_handles_missing_and_blank_docstrings():
    from opentargets_mcp.server import _extract_tool_description

    def no_doc():
        pass

    def only_section_doc():
        """**When to use**
        - first line is already a heading
        """

    assert _extract_tool_description(no_doc) is None
    assert _extract_tool_description(only_section_doc) is None


def test_declared_versions_stay_in_sync():
    """server.json drifted to 0.4.0 while the package said 0.5.0."""
    import json

    from opentargets_mcp import __version__

    pyproject = pathlib.Path("pyproject.toml").read_text()
    declared = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1)
    assert declared == __version__

    server = json.loads(pathlib.Path("server.json").read_text())
    assert server["version"] == __version__
    for package in server["packages"]:
        assert package["version"] == __version__

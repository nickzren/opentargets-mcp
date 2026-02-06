import aiohttp
import pytest

from opentargets_mcp.exceptions import ValidationError
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.settings import ServerSettings
from opentargets_mcp.tools.evidence import EvidenceApi
from opentargets_mcp.tools.graphql import GraphqlApi
from opentargets_mcp.tools.search import SearchApi
from opentargets_mcp.tools.study import StudyApi
from opentargets_mcp.tools.target import TargetApi
from opentargets_mcp.tools.variant import VariantApi
import opentargets_mcp.tools.graphql as graphql_module
from opentargets_mcp.utils import validate_required_int


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
    with pytest.raises(
        ValidationError,
        match=f"page_size must be <= {server_module.MAX_PAGE_SIZE}.",
    ):
        await wrapper(page_size=server_module.MAX_PAGE_SIZE + 1)


def test_server_main_rejects_port_above_tcp_max(monkeypatch):
    import opentargets_mcp.server as server_module

    monkeypatch.setattr("sys.argv", ["opentargets-mcp", "--port", "65536"])
    with pytest.raises(SystemExit) as exc:
        server_module.main()
    assert exc.value.code == 2


@pytest.mark.asyncio
async def test_tool_wrapper_rejects_bool_page_size(monkeypatch):
    import opentargets_mcp.server as server_module

    async def fake_tool(_client, page_size: int):
        return {"page_size": page_size}

    monkeypatch.setattr(server_module, "get_client", lambda: object())

    wrapper = server_module._make_tool_wrapper(fake_tool)
    with pytest.raises(ValidationError, match="page_size must be an integer >= 1."):
        await wrapper(page_size=True)


def test_validate_required_int_rejects_bool():
    with pytest.raises(ValidationError, match="size must be an integer >= 1."):
        validate_required_int(True, "size")


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
async def test_target_expression_supports_fields_projection():
    class _FakeClient:
        async def _query(self, *_args, **_kwargs):
            return {
                "target": {
                    "id": "ENSG00000157764",
                    "expressions": [
                        {
                            "tissue": {"label": "Liver"},
                            "rna": {"level": "medium"},
                        }
                    ],
                }
            }

    api = TargetApi()
    result = await api.get_target_expression(
        _FakeClient(),
        "ENSG00000157764",
        fields=["target.expressions.tissue.label"],
    )
    assert result == {
        "target": {
            "expressions": [
                {
                    "tissue": {
                        "label": "Liver",
                    }
                }
            ]
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

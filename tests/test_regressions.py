import aiohttp
import pytest

from opentargets_mcp.exceptions import ValidationError
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.graphql import GraphqlApi
from opentargets_mcp.tools.search import SearchApi
import opentargets_mcp.tools.graphql as graphql_module


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

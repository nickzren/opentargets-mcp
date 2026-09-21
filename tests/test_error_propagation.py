"""Regression tests for upstream GraphQL error propagation.

Covers the two failure modes reported in issue #4:
  * HTTP 400 from the Platform API (e.g. a field removed by a data release)
  * HTTP 200 carrying a non-empty ``errors`` array

Both must reach the MCP client with actionable text rather than being reduced
to the generic ``Error calling tool '<name>'`` produced by ``mask_error_details``.
"""

import json

import pytest
from fastmcp import Client

import opentargets_mcp.server as server_module
from opentargets_mcp.exceptions import NetworkError, UpstreamQueryError
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.graphql import GraphqlApi

from .test_regressions import _FakeResponse, _FakeSession

MISSING_FIELD_MESSAGE = (
    "Cannot query field 'maximumClinicalTrialPhase' on type 'Drug'. "
    "Did you mean 'maximumClinicalStage'?"
)

BAD_REQUEST_BODY = json.dumps({"errors": [{"message": MISSING_FIELD_MESSAGE}]})

PARTIAL_DATA_BODY = json.dumps(
    {
        "data": {"target": None},
        "errors": [{"message": MISSING_FIELD_MESSAGE}],
    }
)

GOOD_BODY = json.dumps({"data": {"target": {"id": "ENSG00000157764"}}})


def _client_with(bodies, status=200):
    """Build a client whose session replays the given response bodies."""
    client = OpenTargetsClient(max_retries=1, retry_delay=0)
    client.session = _FakeSession(
        [_FakeResponse(status, body) for body in bodies]
    )
    return client


# ---------------------------------------------------------------------------
# Client layer: _query must surface upstream GraphQL messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_raises_upstream_error_with_message_on_http_400():
    client = _client_with([BAD_REQUEST_BODY], status=400)

    with pytest.raises(UpstreamQueryError) as exc_info:
        await client._query("{ target { id } }")

    assert MISSING_FIELD_MESSAGE in str(exc_info.value)


@pytest.mark.asyncio
async def test_query_raises_upstream_error_on_http_200_with_errors():
    client = _client_with([PARTIAL_DATA_BODY])

    with pytest.raises(UpstreamQueryError) as exc_info:
        await client._query("{ target { id } }")

    assert MISSING_FIELD_MESSAGE in str(exc_info.value)


@pytest.mark.asyncio
async def test_failed_query_is_not_cached():
    """A degraded response must not poison the cache for the TTL."""
    client = _client_with([PARTIAL_DATA_BODY, GOOD_BODY])

    with pytest.raises(UpstreamQueryError):
        await client._query("{ target { id } }")

    # Same cache key: must hit the network again rather than replay the failure.
    result = await client._query("{ target { id } }")
    assert result == {"target": {"id": "ENSG00000157764"}}


@pytest.mark.asyncio
async def test_non_graphql_http_failure_still_raises_network_error():
    """Transport-level failures must not be relabelled as upstream query errors."""
    client = _client_with(["<html>502 Bad Gateway</html>"], status=502)

    with pytest.raises(NetworkError):
        await client._query("{ target { id } }")


@pytest.mark.asyncio
async def test_successful_query_shape_is_unchanged():
    client = _client_with([GOOD_BODY])

    assert await client._query("{ target { id } }") == {
        "target": {"id": "ENSG00000157764"}
    }


# ---------------------------------------------------------------------------
# graphql.py must keep its documented partial-data behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raw_graphql_tool_still_returns_partial_data_as_warning():
    client = _client_with([PARTIAL_DATA_BODY])

    result = await GraphqlApi().graphql_query(client, "{ target { id } }")

    assert result["status"] == "warning"
    assert result["result"] == {"target": None}
    assert result["message"]


# ---------------------------------------------------------------------------
# MCP boundary: the message must survive mask_error_details
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_server_client(monkeypatch):
    """Point the server's shared client at a replayed response."""

    def _install(bodies, status=200):
        client = _client_with(bodies, status=status)
        monkeypatch.setattr(server_module, "get_client", lambda: client)
        return client

    return _install


def _error_text(result) -> str:
    return " ".join(
        block.text for block in result.content if getattr(block, "text", None)
    )


@pytest.mark.asyncio
async def test_tool_call_reports_graphql_message_on_http_400(stub_server_client):
    stub_server_client([BAD_REQUEST_BODY], status=400)

    async with Client(server_module.mcp) as mcp_client:
        result = await mcp_client.call_tool(
            "get_target_info",
            {"ensembl_id": "ENSG00000157764"},
            raise_on_error=False,
        )

    assert result.is_error
    assert MISSING_FIELD_MESSAGE in _error_text(result)


@pytest.mark.asyncio
async def test_tool_call_reports_graphql_message_on_http_200_with_errors(
    stub_server_client,
):
    stub_server_client([PARTIAL_DATA_BODY])

    async with Client(server_module.mcp) as mcp_client:
        result = await mcp_client.call_tool(
            "get_target_info",
            {"ensembl_id": "ENSG00000157764"},
            raise_on_error=False,
        )

    assert result.is_error
    assert MISSING_FIELD_MESSAGE in _error_text(result)


@pytest.mark.asyncio
async def test_unexpected_exception_stays_masked(monkeypatch):
    """Masking must still hide incidental internals."""

    def _boom():
        raise RuntimeError("psycopg2://user:hunter2@internal-host/db")

    monkeypatch.setattr(server_module, "get_client", _boom)

    async with Client(server_module.mcp) as mcp_client:
        result = await mcp_client.call_tool(
            "get_target_info",
            {"ensembl_id": "ENSG00000157764"},
            raise_on_error=False,
        )

    assert result.is_error
    assert "hunter2" not in _error_text(result)

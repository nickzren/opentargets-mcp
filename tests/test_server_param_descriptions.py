"""Shared argument descriptions applied by the tool wrapper."""

import inspect
import json
from typing import List, Optional

import pytest
from fastmcp import Client

import opentargets_mcp.server as server_module
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.meta import MetaApi

from .test_regressions import _FakeResponse, _FakeSession

DESCRIPTIONS = server_module._PARAM_DESCRIPTIONS


@pytest.mark.asyncio
async def test_every_shared_description_reaches_the_input_schema():
    async with Client(server_module.mcp) as mcp_client:
        tools = await mcp_client.list_tools()

    described = set()
    for tool in tools:
        for name, schema in tool.inputSchema["properties"].items():
            if name in DESCRIPTIONS:
                assert schema["description"] == DESCRIPTIONS[name], (tool.name, name)
                described.add(name)

    assert described == set(DESCRIPTIONS)


def test_wrapper_keeps_signature_and_leaves_method_annotations_alone():
    method = MetaApi().map_ids
    wrapper = server_module._make_tool_wrapper(method)

    assert list(inspect.signature(wrapper).parameters) == list(
        inspect.signature(method).parameters
    )[1:]
    assert method.__annotations__["entity_names"] == Optional[List[str]]


@pytest.mark.asyncio
async def test_described_arguments_still_validate_and_pass_through(monkeypatch):
    client = OpenTargetsClient(max_retries=1)
    client.session = _FakeSession(
        [
            _FakeResponse(
                200,
                json.dumps(
                    {"data": {"disease": {"id": "MONDO_0005105", "name": "melanoma"}}}
                ),
            )
        ]
    )
    monkeypatch.setattr(server_module, "get_client", lambda: client)

    async with Client(server_module.mcp) as mcp_client:
        result = await mcp_client.call_tool(
            "get_disease_info",
            {"efo_id": "MONDO:0005105", "fields": ["disease.name"]},
        )

    assert result.structured_content == {"disease": {"name": "melanoma"}}

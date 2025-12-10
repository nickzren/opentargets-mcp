"""FastMCP-backed server for Open Targets MCP tools."""
from __future__ import annotations

import anyio
import functools
import inspect
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Callable, NamedTuple, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
import mcp.types as mcp_types

from .queries import OpenTargetsClient
from .tools.disease import DiseaseApi
from .tools.drug import DrugApi
from .tools.evidence import EvidenceApi
from .tools.meta import MetaApi
from .tools.search import SearchApi
from .tools.study import StudyApi
from .tools.target import TargetApi
from .tools.variant import VariantApi
from mcp.server.lowlevel.server import NotificationOptions

__all__ = [
    "mcp",
    "get_client",
    "main",
]

# ---------------------------------------------------------------------------
# Logging & environment setup
# ---------------------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client lifecycle management
# ---------------------------------------------------------------------------
_client: Optional[OpenTargetsClient] = None


def get_client() -> OpenTargetsClient:
    """Return the active OpenTargetsClient or raise if not initialised."""
    if _client is None:
        raise RuntimeError(
            "OpenTargetsClient not initialised. Tools must be called through the "
            "running MCP server."
        )
    return _client


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialise and clean up shared resources for FastMCP."""
    global _client

    logger.info("Starting Open Targets MCP server")
    api_url = os.getenv("OPEN_TARGETS_API_URL")
    if api_url is not None:
        _client = OpenTargetsClient(base_url=api_url)
    else:
        _client = OpenTargetsClient()
    await _client._ensure_session()

    try:
        yield
    finally:
        if _client is not None:
            await _client.close()
            _client = None
            logger.info("Open Targets MCP server shut down cleanly")


# ---------------------------------------------------------------------------
# FastMCP initialisation
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="opentargets",
    version="0.2.0",
    lifespan=lifespan,
)

_target_api = TargetApi()
_disease_api = DiseaseApi()
_drug_api = DrugApi()
_evidence_api = EvidenceApi()
_search_api = SearchApi()
_variant_api = VariantApi()
_study_api = StudyApi()
_meta_api = MetaApi()


class _ToolDocMetadata(NamedTuple):
    title: str | None
    description: str | None


def _extract_tool_doc_metadata(method: Callable[..., Any]) -> _ToolDocMetadata:
    """Convert a method docstring into FastMCP metadata."""
    doc = inspect.getdoc(method)
    if not doc:
        return _ToolDocMetadata(title=None, description=None)

    lines = doc.splitlines()
    summary = lines[0].strip() if lines else None
    description = doc.strip()
    return _ToolDocMetadata(title=summary, description=description)


def _make_tool_wrapper(method: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap an API coroutine so the shared client is injected automatically."""

    @functools.wraps(method)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        client = get_client()
        return await method(client, *args, **kwargs)

    signature = inspect.signature(method)
    params = list(signature.parameters.values())[1:]
    wrapper.__signature__ = signature.replace(parameters=params)  # type: ignore[attr-defined]

    # Preserve the original method docstring for tooling and auto-generated metadata.
    wrapper.__doc__ = inspect.getdoc(method)

    return wrapper


def register_all_api_methods() -> None:
    """Register every coroutine defined on the API mixins as FastMCP tools."""
    api_instances = (
        _target_api,
        _disease_api,
        _drug_api,
        _evidence_api,
        _search_api,
        _variant_api,
        _study_api,
        _meta_api,
    )

    for api in api_instances:
        for name in dir(api):
            if name.startswith("_"):
                continue
            method = getattr(api, name)
            if not inspect.iscoroutinefunction(method):
                continue
            if name in getattr(mcp._tool_manager, "_tools", {}):
                logger.debug("Tool already registered: %s", name)
                continue
            wrapper = _make_tool_wrapper(method)
            doc_meta = _extract_tool_doc_metadata(method)
            tool_decorator = mcp.tool(
                name=name,
                description=doc_meta.description,
            )
            tool_decorator(wrapper)
            logger.debug("Registered tool: %s", name)


register_all_api_methods()


# ---------------------------------------------------------------------------
# Deprecated module-level guidance
# ---------------------------------------------------------------------------

def __getattr__(name: str) -> Any:  # pragma: no cover - guidance only
    if name == "ALL_TOOLS":
        raise AttributeError(
            "ALL_TOOLS has been removed in v0.2.0. Use FastMCP list_tools instead."
        )
    if name == "API_CLASS_MAP":
        raise AttributeError(
            "API_CLASS_MAP has been removed in v0.2.0. Tool dispatch is handled by FastMCP."
        )
    raise AttributeError(name)


# ---------------------------------------------------------------------------
# Discovery endpoint for HTTP/SSE transports
# ---------------------------------------------------------------------------


@mcp.custom_route("/.well-known/mcp.json", methods=["GET"], include_in_schema=False)
async def discovery_endpoint(request: Request) -> JSONResponse:
    """Expose MCP discovery metadata for HTTP/SSE clients."""

    base_url = str(request.base_url).rstrip("/")
    sse_path = mcp._deprecated_settings.sse_path.lstrip("/")
    message_path = mcp._deprecated_settings.message_path.lstrip("/")
    http_path = mcp._deprecated_settings.streamable_http_path.lstrip("/")

    capabilities = mcp._mcp_server.get_capabilities(
        NotificationOptions(),
        experimental_capabilities={}
    )

    transports: dict[str, dict[str, str]] = {
        "sse": {
            "url": f"{base_url}/{sse_path}",
            "messageUrl": f"{base_url}/{message_path}",
        }
    }

    transports["http"] = {
        "url": f"{base_url}/{http_path}",
    }

    discovery = {
        "protocolVersion": mcp_types.LATEST_PROTOCOL_VERSION,
        "server": {
            "name": mcp._mcp_server.name,
            "version": mcp._mcp_server.version,
            "instructions": mcp._mcp_server.instructions,
        },
        "capabilities": capabilities.model_dump(mode="json"),
        "transports": transports,
    }

    return JSONResponse(discovery)


@mcp.custom_route("/", methods=["GET"], include_in_schema=False)
async def root_health(_: Request) -> JSONResponse:
    """Simple health check endpoint."""

    return JSONResponse({"status": "ok"})


@mcp.custom_route(mcp._deprecated_settings.sse_path, methods=["POST"], include_in_schema=False)
async def sse_message_fallback(_: Request) -> Response:
    """Gracefully handle clients that POST to the SSE endpoint."""

    return Response(status_code=204)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Open Targets MCP Server",
        epilog="Environment overrides: MCP_TRANSPORT, FASTMCP_SERVER_HOST, FASTMCP_SERVER_PORT",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport protocol to expose (stdio, sse, or http)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("FASTMCP_SERVER_HOST", "0.0.0.0"),
        help="Host for SSE transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("FASTMCP_SERVER_PORT", "8000")),
        help="Port for SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG level) logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.transport in {"sse", "http"}:
        os.environ["FASTMCP_SERVER_HOST"] = args.host
        os.environ["FASTMCP_SERVER_PORT"] = str(args.port)
        if hasattr(mcp, "settings"):
            mcp.settings.host = args.host  # type: ignore[attr-defined]
            mcp.settings.port = args.port  # type: ignore[attr-defined]
        logger.info("Configured %s host=%s port=%s", args.transport.upper(), args.host, args.port)

    logger.info(
        "Starting Open Targets MCP server (transport=%s, host=%s, port=%s)",
        args.transport,
        args.host,
        args.port,
    )

    api_url = os.getenv("OPEN_TARGETS_API_URL")
    if api_url is not None:
        logger.info("Using Open Targets API URL: %s", api_url)
    else:
        logger.info("Using default Open Targets API URL")

    try:
        if args.transport == "http":
            async def run_http():
                await mcp.run_http_async(host=args.host, port=args.port)

            anyio.run(run_http)
        else:
            mcp.run(transport=args.transport)
    except KeyboardInterrupt:  # pragma: no cover - user interaction
        logger.info("Server interrupted by user")
    except Exception:  # pragma: no cover - unexpected runtime failure
        logger.exception("Server encountered an unrecoverable error")
        raise


if __name__ == "__main__":  # pragma: no cover
    main()

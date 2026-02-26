"""FastMCP-backed server for Open Targets MCP tools."""

from __future__ import annotations

import anyio
import fastmcp
import functools
import inspect
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
import mcp.types as mcp_types

from . import __version__
from .exceptions import ValidationError
from .queries import OpenTargetsClient
from .settings import ServerSettings
from .tools.disease import DiseaseApi
from .tools.drug import DrugApi
from .tools.evidence import EvidenceApi
from .tools.graphql import GraphqlApi
from .tools.meta import MetaApi
from .tools.search import SearchApi
from .tools.study import StudyApi
from .tools.target import TargetApi
from .tools.variant import VariantApi
from .tools.workflows import WorkflowApi
from .resolver import resolve_params

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
MAX_PAGE_SIZE = 500


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
    settings = ServerSettings()
    _client = OpenTargetsClient(base_url=str(settings.open_targets_api_url))
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
    version=__version__,
    instructions=(
        "Tool selection policy:\n"
        "1) If you have a name/symbol, call the relevant tool directly (IDs are auto-resolved).\n"
        "2) Use get_{entity}_info for basic lookup.\n"
        "3) Use get_{entity}_associated_* for relationships.\n"
        "4) Use get_{entity}_known_drugs for therapeutics.\n"
        "5) Use fields=[...] to limit output when you only need specific fields.\n"
        "6) If a name fails to resolve, call search_entities to find the canonical ID.\n"
        "7) Use graphql_query only if no curated tool fits.\n"
        "8) Use workflow tools for multi-hop disease-target-drug prioritisation.\n"
    ),
    mask_error_details=True,
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
_graphql_api = GraphqlApi()
_workflow_api = WorkflowApi()


def _extract_tool_description(method: Callable[..., Any]) -> str | None:
    """Extract docstring from a method for FastMCP metadata."""
    doc = inspect.getdoc(method)
    return doc.strip() if doc else None


def _make_tool_wrapper(method: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap an API coroutine so the shared client is injected automatically."""
    signature = inspect.signature(method)

    @functools.wraps(method)
    async def wrapper(**kwargs: Any) -> Any:
        client = get_client()
        resolved = await resolve_params(client, kwargs)
        if "page_index" in resolved:
            page_index = resolved["page_index"]
            if not isinstance(page_index, int) or isinstance(page_index, bool) or page_index < 0:
                raise ValidationError("page_index must be an integer >= 0.")
        if "page_size" in resolved:
            page_size = resolved["page_size"]
            if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size < 1:
                raise ValidationError("page_size must be an integer >= 1.")
            if page_size > MAX_PAGE_SIZE:
                raise ValidationError(
                    f"page_size must be <= {MAX_PAGE_SIZE}."
                )
        return await method(client, **resolved)

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
        _workflow_api,
    )

    if _graphql_api is not None:
        api_instances = (*api_instances, _graphql_api)

    for api in api_instances:
        for name in dir(api):
            if name.startswith("_"):
                continue
            method = getattr(api, name)
            if not inspect.iscoroutinefunction(method):
                continue
            wrapper = _make_tool_wrapper(method)
            description = _extract_tool_description(method)
            tool_decorator = mcp.tool(
                name=name,
                description=description,
                annotations={"readOnlyHint": True},
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
    sse_path = fastmcp.settings.sse_path.lstrip("/")
    message_path = fastmcp.settings.message_path.lstrip("/")
    http_path = fastmcp.settings.streamable_http_path.lstrip("/")

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
            "name": mcp.name,
            "version": mcp.version,
            "instructions": mcp.instructions,
        },
        "capabilities": mcp_types.ServerCapabilities(
            tools=mcp_types.ToolsCapability(listChanged=True)
        ).model_dump(mode="json"),
        "transports": transports,
    }

    return JSONResponse(discovery)


@mcp.custom_route("/", methods=["GET"], include_in_schema=False)
async def root_health(_: Request) -> JSONResponse:
    """Simple health check endpoint."""

    return JSONResponse({"status": "ok"})


@mcp.custom_route(fastmcp.settings.sse_path, methods=["POST"], include_in_schema=False)
async def sse_message_fallback(_: Request) -> Response:
    """Gracefully handle clients that POST to the SSE endpoint."""

    return Response(status_code=204)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    import argparse

    settings = ServerSettings()

    parser = argparse.ArgumentParser(
        description="Open Targets MCP Server",
        epilog=(
            "Environment overrides: MCP_TRANSPORT, FASTMCP_SERVER_HOST, "
            "FASTMCP_SERVER_PORT, OPEN_TARGETS_API_URL, "
            "OPEN_TARGETS_RATE_LIMIT_ENABLED, OPEN_TARGETS_RATE_LIMIT_RPS, "
            "OPEN_TARGETS_RATE_LIMIT_BURST"
        ),
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print package version and exit",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List available tools and exit",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http"],
        default=settings.mcp_transport,
        help="Transport protocol to expose (stdio, sse, or http)",
    )
    parser.add_argument(
        "--host",
        default=settings.fastmcp_server_host,
        help="Host for SSE transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.fastmcp_server_port,
        help="Port for SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--api",
        default=str(settings.open_targets_api_url),
        help="Open Targets GraphQL endpoint URL",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG level) logging",
    )
    parser.add_argument(
        "--rate-limiting",
        action="store_true",
        default=settings.open_targets_rate_limit_enabled,
        help="Enable global rate limiting with default/custom settings",
    )
    parser.add_argument(
        "--rate-limit-rps",
        type=float,
        default=settings.open_targets_rate_limit_rps,
        help="Enable global rate limiting with this max requests/second (0 disables)",
    )
    parser.add_argument(
        "--rate-limit-burst",
        type=int,
        default=settings.open_targets_rate_limit_burst,
        help="Burst capacity used when rate limiting is enabled",
    )

    args = parser.parse_args()

    if args.version:
        print(f"opentargets-mcp {__version__}")
        return

    if args.list_tools:
        async def collect_tools() -> list[Any] | dict[str, Any]:
            return await mcp.list_tools()

        tools = anyio.run(collect_tools)
        if isinstance(tools, dict):
            entries = sorted(tools.items(), key=lambda item: item[0])
        else:
            entries = sorted(((tool.name, tool) for tool in tools), key=lambda item: item[0])

        for name, tool in entries:
            description = (tool.description or "").strip().splitlines()
            first_line = description[0] if description else "No description available"
            print(f"{name}: {first_line}")
        return

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.port < 1:
        parser.error("--port must be >= 1")
    if args.port > 65535:
        parser.error("--port must be <= 65535")
    if args.rate_limit_burst < 1:
        parser.error("--rate-limit-burst must be >= 1")
    if args.rate_limit_rps < 0:
        parser.error("--rate-limit-rps must be >= 0")

    if args.api:
        os.environ["OPEN_TARGETS_API_URL"] = args.api

    if args.rate_limiting and args.rate_limit_rps == 0:
        # Sensible defaults when enable-only mode is requested.
        args.rate_limit_rps = 3.0
        if args.rate_limit_burst == settings.open_targets_rate_limit_burst:
            args.rate_limit_burst = 100

    if args.transport in {"sse", "http"}:
        os.environ["FASTMCP_SERVER_HOST"] = args.host
        os.environ["FASTMCP_SERVER_PORT"] = str(args.port)
        fastmcp.settings.host = args.host
        fastmcp.settings.port = args.port
        logger.info(
            "Configured %s host=%s port=%s",
            args.transport.upper(),
            args.host,
            args.port,
        )

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

    if args.rate_limit_rps > 0:
        from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

        mcp.add_middleware(
            RateLimitingMiddleware(
                max_requests_per_second=args.rate_limit_rps,
                burst_capacity=args.rate_limit_burst,
                global_limit=True,
            )
        )
        logger.info(
            "Enabled global rate limiting: %.2f req/s (burst=%s)",
            args.rate_limit_rps,
            args.rate_limit_burst,
        )

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

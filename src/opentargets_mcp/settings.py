"""Validated runtime settings for the Open Targets MCP server."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = SettingsConfigDict(extra="ignore")

    mcp_transport: Literal["stdio", "sse", "http"] = Field(
        default="stdio",
        alias="MCP_TRANSPORT",
    )
    fastmcp_server_host: str = Field(default="0.0.0.0", alias="FASTMCP_SERVER_HOST")
    fastmcp_server_port: int = Field(
        default=8000,
        alias="FASTMCP_SERVER_PORT",
        ge=1,
        le=65535,
    )
    open_targets_api_url: HttpUrl = Field(
        default=HttpUrl("https://api.platform.opentargets.org/api/v4/graphql"),
        alias="OPEN_TARGETS_API_URL",
    )
    open_targets_rate_limit_enabled: bool = Field(
        default=False,
        alias="OPEN_TARGETS_RATE_LIMIT_ENABLED",
    )
    open_targets_rate_limit_rps: float = Field(
        default=0.0,
        alias="OPEN_TARGETS_RATE_LIMIT_RPS",
        ge=0,
    )
    open_targets_rate_limit_burst: int = Field(
        default=20,
        alias="OPEN_TARGETS_RATE_LIMIT_BURST",
        ge=1,
    )

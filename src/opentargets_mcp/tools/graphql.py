"""Advanced GraphQL tooling."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, Optional

from graphql import build_client_schema, get_introspection_query, print_schema

from ..exceptions import NetworkError, ValidationError
from ..queries import OpenTargetsClient

logger = logging.getLogger(__name__)

_MUTATION_PATTERN = re.compile(r"^\s*mutation\b", re.IGNORECASE)

_SCHEMA_CACHE_TTL = 3600
_schema_cache: dict[str, Any] = {}
_schema_cache_lock = asyncio.Lock()

_INTROSPECTION_QUERY = get_introspection_query()


class GraphqlApi:
    """Raw GraphQL tools for advanced users."""

    async def graphql_schema(self, client: OpenTargetsClient) -> str:
        """ADVANCED: Return the GraphQL schema in SDL format.

        **Use only when** you need to discover fields not covered by specialized tools.
        """
        current_time = time.time()

        async with _schema_cache_lock:
            cached_schema = _schema_cache.get("schema")
            cached_timestamp = _schema_cache.get("timestamp")
            if cached_schema and cached_timestamp and (current_time - cached_timestamp) < _SCHEMA_CACHE_TTL:
                return cached_schema

            introspection = await client._query(_INTROSPECTION_QUERY)
            try:
                schema = build_client_schema(introspection)
                schema_sdl = print_schema(schema)
            except Exception as exc:  # pragma: no cover - defensive
                raise ValidationError(f"Failed to build schema from introspection: {exc}") from exc

            _schema_cache["schema"] = schema_sdl
            _schema_cache["timestamp"] = current_time
            return schema_sdl

    async def graphql_query(
        self,
        client: OpenTargetsClient,
        query_string: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """ADVANCED: Execute a raw GraphQL query against Open Targets.

        **Use only when** no specialized tool exists for your query.
        **Do not use** for mutations (read-only access only).

        **Returns**
        - `Dict[str, Any]`: QueryResult envelope with `status`, `result`, and optional `message`.
        """
        if _MUTATION_PATTERN.search(query_string):
            raise ValidationError("graphql_query does not support mutations.")

        await client._ensure_session()

        payload: Dict[str, Any] = {"query": query_string}
        if variables is not None:
            payload["variables"] = variables
        if operation_name is not None:
            payload["operationName"] = operation_name

        try:
            async with client.session.post(  # type: ignore[union-attr]
                client.base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                response_text = await response.text()
                if not response.ok:
                    logger.error(
                        "GraphQL HTTP error %s for %s: %s",
                        response.status,
                        response.url,
                        response_text,
                    )
                    response.raise_for_status()
                try:
                    payload = await response.json()
                except Exception:
                    payload = json.loads(response_text)
                return _wrap_query_result(payload)
        except Exception as exc:
            raise NetworkError(f"GraphQL request failed: {exc}") from exc


def _wrap_query_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    errors = payload.get("errors")
    data = payload.get("data")
    if errors and not data:
        return {"status": "error", "result": None, "message": errors}
    if errors:
        return {"status": "warning", "result": data, "message": errors}
    return {"status": "success", "result": data, "message": None}

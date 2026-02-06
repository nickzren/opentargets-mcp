"""Advanced GraphQL tooling."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, Optional

import aiohttp
from graphql import (
    OperationDefinitionNode,
    build_client_schema,
    get_introspection_query,
    parse,
    print_schema,
)

from ..exceptions import NetworkError, ValidationError
from ..queries import OpenTargetsClient

logger = logging.getLogger(__name__)

_MUTATION_PATTERN = re.compile(r"^\s*mutation\b", re.IGNORECASE)

_SCHEMA_CACHE_TTL = 3600
_schema_cache: dict[str, dict[str, Any]] = {}
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
            cache_entry = _schema_cache.get(client.base_url)
            if (
                cache_entry
                and (current_time - cache_entry["timestamp"]) < _SCHEMA_CACHE_TTL
            ):
                return cache_entry["schema"]

            introspection = await client._query(_INTROSPECTION_QUERY)
            try:
                schema = build_client_schema(introspection)
                schema_sdl = print_schema(schema)
            except Exception as exc:  # pragma: no cover - defensive
                raise ValidationError(
                    f"Failed to build schema from introspection: {exc}"
                ) from exc

            _schema_cache[client.base_url] = {
                "schema": schema_sdl,
                "timestamp": current_time,
            }
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
        if _contains_mutation(query_string):
            raise ValidationError("graphql_query does not support mutations.")

        await client._ensure_session()

        payload: Dict[str, Any] = {"query": query_string}
        if variables is not None:
            payload["variables"] = variables
        if operation_name is not None:
            payload["operationName"] = operation_name

        max_retries = getattr(client, "_max_retries", 3)
        retry_delay = getattr(client, "_retry_delay", 1.0)
        last_exception: Exception | None = None

        for attempt in range(max_retries):
            try:
                async with client.session.post(  # type: ignore[union-attr]
                    client.base_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    response_text = await response.text()
                    response_payload = _try_parse_payload(response_text)

                    if response.ok:
                        if response_payload is None:
                            return {
                                "status": "error",
                                "result": None,
                                "message": [
                                    {
                                        "message": "Non-JSON response from GraphQL endpoint"
                                    }
                                ],
                            }
                        return _wrap_query_result(response_payload)

                    logger.error(
                        "GraphQL HTTP error %s for %s: %s",
                        response.status,
                        response.url,
                        response_text,
                    )

                    if (
                        _is_retryable_status(response.status)
                        and attempt < max_retries - 1
                    ):
                        await asyncio.sleep(retry_delay * (2**attempt))
                        continue

                    if response_payload is not None and (
                        "errors" in response_payload or "data" in response_payload
                    ):
                        return _wrap_query_result(response_payload)

                    return {
                        "status": "error",
                        "result": None,
                        "message": [
                            {"message": response_text or f"HTTP {response.status}"}
                        ],
                    }

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exception = exc
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2**attempt))
                    continue
                raise NetworkError(f"GraphQL request failed: {exc}") from exc
            except Exception as exc:
                raise NetworkError(f"GraphQL request failed: {exc}") from exc

        if last_exception is not None:
            raise NetworkError(
                f"GraphQL request failed after {max_retries} retries"
            ) from last_exception

        raise NetworkError("GraphQL request failed without making any attempts")


def _wrap_query_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    errors = payload.get("errors")
    data = payload.get("data")
    if errors and not data:
        return {"status": "error", "result": None, "message": errors}
    if errors:
        return {"status": "warning", "result": data, "message": errors}
    return {"status": "success", "result": data, "message": None}


def _try_parse_payload(response_text: str) -> Dict[str, Any] | None:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _is_retryable_status(status: int) -> bool:
    return status >= 500 or status == 429


def _contains_mutation(query_string: str) -> bool:
    try:
        document = parse(query_string)
    except Exception:
        return bool(_MUTATION_PATTERN.search(query_string))

    for definition in document.definitions:
        if not isinstance(definition, OperationDefinitionNode):
            continue
        operation = getattr(
            definition.operation, "value", str(definition.operation)
        ).lower()
        if operation == "mutation":
            return True
    return False

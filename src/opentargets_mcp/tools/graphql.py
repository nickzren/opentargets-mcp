"""Advanced GraphQL tooling."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import weakref
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

_MUTATION_PATTERN = re.compile(r"\bmutation\b", re.IGNORECASE)

_SCHEMA_CACHE_TTL = 3600
_schema_cache: dict[str, dict[str, Any]] = {}
_schema_cache_locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = (
    weakref.WeakKeyDictionary()
)

_INTROSPECTION_QUERY = get_introspection_query()
MAX_GRAPHQL_BATCH_ITEMS = 500
MAX_GRAPHQL_BATCH_CONCURRENCY = 20


class GraphqlApi:
    """Raw GraphQL tools for advanced users."""

    async def graphql_schema(self, client: OpenTargetsClient) -> str:
        """ADVANCED: Return the GraphQL schema in SDL format.

        **Use only when** you need to discover fields not covered by specialized tools.
        """
        current_time = time.time()

        async with _get_schema_cache_lock():
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

    async def graphql_batch_query(
        self,
        client: OpenTargetsClient,
        query_string: str,
        variables_list: list[Dict[str, Any]],
        key_field: Optional[str] = None,
        operation_name: Optional[str] = None,
        max_concurrency: int = 4,
    ) -> Dict[str, Any]:
        """Execute one GraphQL query against many variable sets.

        **When to use**
        - You need to run the same query for many IDs in one tool call.
        - You want an aggregated success/warning/error summary.

        **Parameters**
        - `query_string`: GraphQL query string.
        - `variables_list`: List of variable dictionaries, one per execution.
        - `key_field`: Optional variable key to copy into each result item.
        - `operation_name`: Optional GraphQL operation name.
        - `max_concurrency`: Max in-flight requests (default 4).
          Maximum allowed is `MAX_GRAPHQL_BATCH_CONCURRENCY`.

        **Returns**
        - `Dict[str, Any]`:
          `{"status", "summary", "results"}` where `results` items contain
          `index`, `key`, and per-query `result` envelope.
        """
        if not variables_list:
            raise ValidationError("variables_list cannot be empty.")
        if len(variables_list) > MAX_GRAPHQL_BATCH_ITEMS:
            raise ValidationError(
                f"variables_list cannot exceed {MAX_GRAPHQL_BATCH_ITEMS} items."
            )
        if max_concurrency < 1:
            raise ValidationError("max_concurrency must be >= 1.")
        if max_concurrency > MAX_GRAPHQL_BATCH_CONCURRENCY:
            raise ValidationError(
                "max_concurrency must be <= "
                f"{MAX_GRAPHQL_BATCH_CONCURRENCY}."
            )

        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_single(index: int, item: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(item, dict):
                return {
                    "index": index,
                    "key": None,
                    "result": {
                        "status": "error",
                        "result": None,
                        "message": [{"message": "Each variables_list entry must be an object"}],
                    },
                }

            key = str(item.get(key_field)) if key_field and key_field in item else None
            try:
                async with semaphore:
                    result = await self.graphql_query(
                        client=client,
                        query_string=query_string,
                        variables=item,
                        operation_name=operation_name,
                    )
            except Exception as exc:  # pragma: no cover - defensive boundary
                result = {
                    "status": "error",
                    "result": None,
                    "message": [{"message": str(exc)}],
                }

            return {
                "index": index,
                "key": key,
                "result": result,
            }

        results = await asyncio.gather(
            *(run_single(index, variables) for index, variables in enumerate(variables_list))
        )

        successful = sum(1 for item in results if item["result"].get("status") == "success")
        warning = sum(1 for item in results if item["result"].get("status") == "warning")
        failed = sum(1 for item in results if item["result"].get("status") == "error")

        if failed:
            overall_status = "warning" if (successful or warning) else "error"
        elif warning:
            overall_status = "warning"
        else:
            overall_status = "success"

        return {
            "status": overall_status,
            "summary": {
                "total": len(results),
                "successful": successful,
                "warning": warning,
                "failed": failed,
            },
            "results": results,
        }


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


def _get_schema_cache_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _schema_cache_locks.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _schema_cache_locks[loop] = lock
    return lock


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

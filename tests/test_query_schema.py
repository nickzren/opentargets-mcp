"""Every GraphQL query embedded in the package must validate against the API schema.

Offline, queries are checked against the committed snapshot
tests/fixtures/schema.graphql; `uv run pytest -m live tests/test_query_schema.py`
checks them against the live API instead. Refresh the snapshot after an Open
Targets data release with `uv run python -m tests.test_query_schema`.
"""

import ast
import asyncio
import pathlib
import re

from graphql import (
    GraphQLError,
    build_client_schema,
    build_schema,
    get_introspection_query,
    parse,
    print_schema,
    validate,
)

import opentargets_mcp
from opentargets_mcp.queries import OpenTargetsClient

PACKAGE = pathlib.Path(opentargets_mcp.__file__).parent
SNAPSHOT = pathlib.Path(__file__).parent / "fixtures" / "schema.graphql"
# `\b` skips keys such as "queryTerms"; the next character skips the bare "query" key.
QUERY = re.compile(r"^\s*query\b\s*[\w({]")
INTROSPECTION = get_introspection_query(descriptions=False)


def embedded_queries() -> list[tuple[str, str]]:
    return [
        (f"{path.relative_to(PACKAGE.parent)}:{node.lineno}", node.value)
        for path in sorted(PACKAGE.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and QUERY.match(node.value)
    ]


def assert_queries_validate(schema) -> None:
    queries = embedded_queries()
    assert queries, "no embedded queries found"
    problems = []
    for location, query in queries:
        try:
            errors = validate(schema, parse(query))
        except GraphQLError as error:
            errors = [error]
        problems += [f"{location}: {error.message}" for error in errors]
    assert not problems, "\n".join(problems)


def test_embedded_queries_match_the_schema_snapshot():
    assert_queries_validate(build_schema(SNAPSHOT.read_text()))


async def test_embedded_queries_match_the_live_schema(client: OpenTargetsClient):
    assert_queries_validate(build_client_schema(await client._query(INTROSPECTION)))


async def _refresh_snapshot() -> None:
    client = OpenTargetsClient()
    try:
        schema = build_client_schema(await client._query(INTROSPECTION))
        meta = (
            await client._query(
                "query { meta { apiVersion { x y z } dataVersion { year month } } }"
            )
        )["meta"]
    finally:
        await client.close()
    api, data = meta["apiVersion"], meta["dataVersion"]
    SNAPSHOT.write_text(
        f"# Open Targets Platform API {api['x']}.{api['y']}.{api['z']}, "
        f"data {data['year']}.{data['month']}\n{print_schema(schema)}\n"
    )


if __name__ == "__main__":
    asyncio.run(_refresh_snapshot())

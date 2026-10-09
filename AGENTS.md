# Agent Guide — opentargets-mcp

Brief for AI coding agents (Claude Code, Codex) working in this repo or routing biomedical questions through it.

## What this server is
MCP server wrapping the Open Targets Platform GraphQL API. ~68 tools across target, disease, drug, evidence, variant, study, and cross-entity workflows.

## Run locally (stdio)
```bash
uv sync
uv run python -m opentargets_mcp.server          # stdio (default)
uv run opentargets-mcp --list-tools              # inspect catalog
```

HTTP/SSE: append `--transport http --host 127.0.0.1 --port 8000`.

## Use this server for
- Target identity, biology, expression, tractability, safety, mouse phenotypes
- Disease → target prioritisation with scored evidence
- Drug profile, mechanism, adverse events, pharmacovigilance, repurposing
- Variant, GWAS credible sets, L2G predictions, fine-mapped loci
- Cross-entity workflows (`get_drug_repurposing_candidates`, `get_target_disease_evidence`)

Prefer over other servers when the question needs **scored target–disease evidence** or **drug pipeline / clinical-stage data** sourced from ChEMBL/FDA/EMA.

## Triage hints
- Pass names or IDs directly; tools auto-resolve names to canonical IDs. Use `search_entities` (returns `search.triples`) when a name fails to resolve or is ambiguous.
- Use `fields` (dot-paths) on core domain tools to trim payload — large responses are common.
- Use `graphql_batch_query` for many-variable lookups; reserve `graphql_query` / `graphql_schema` for edge cases not covered by curated tools.
- Pagination guardrails: `page_index >= 0`, `page_size 1..500`.

## Pitfalls
- **Strict ID resolution**: unresolved names raise; ambiguous names raise an error listing candidates.
- **Token cost**: omitting `fields` returns the full GraphQL shape — easy to blow context.
- **Rate limits**: `OPEN_TARGETS_RATE_LIMIT_RPS` throttles incoming MCP requests, not upstream Open Targets requests; one tool call can issue many upstream requests (at most 20 concurrent).
- Variant IDs resolve automatically: canonical OT IDs (e.g. `1_55039839_C_T`), rsIDs and `chr`/colon notation. An rsID with several alleles raises an error listing them.

## Source layout
- `src/opentargets_mcp/server.py` — FastMCP entrypoint and tool registration
- `src/opentargets_mcp/tools/` — tool implementations grouped by domain; GraphQL queries live inline here
- `src/opentargets_mcp/queries.py` — HTTP client (`OpenTargetsClient`: retries, cache)
- `src/opentargets_mcp/resolver.py` — name → ID resolution
- `src/opentargets_mcp/settings.py` — typed env config

## Dev
```bash
uv sync --extra dev
uv run ruff check src tests monitoring
uv run pytest -m "not live"                      # offline
uv run pytest -m live                            # live API
```

## When editing tools
1. Write the GraphQL query inline in the tool method under `src/opentargets_mcp/tools/<domain>.py`.
2. Registration is automatic: public coroutines on the `*Api` classes become tools, and the first docstring paragraph is the tool description. Only a new `*Api` class must be added in `server.py`.
3. Update `--list-tools` count in README if the catalog grows.
4. Add a unit test mocking the GraphQL response.

## Release checklist
1. Bump the version in `pyproject.toml`, `server.json` (`version` and `packages[0].version`) and `src/opentargets_mcp/__init__.py`.
2. Push the tag `vX.Y.Z`; the release workflow publishes to PyPI and the MCP registry.
3. After each Open Targets data release, run the live/schema job (`uv run pytest -m live tests/test_query_schema.py` or the monitor workflow) and refresh `tests/fixtures/schema.graphql`.

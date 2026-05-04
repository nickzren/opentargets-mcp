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
- Resolve names to IDs first via `search_entities` (returns `search.triples`).
- Use `fields` (dot-paths) on core domain tools to trim payload — large responses are common.
- Use `graphql_batch_query` for many-variable lookups; reserve `graphql_query` / `graphql_schema` for edge cases not covered by curated tools.
- Pagination guardrails: `page_index >= 0`, `page_size 1..500`.

## Pitfalls
- **Strict ID resolution**: unresolved names raise. Always call `search_entities` if uncertain.
- **Token cost**: omitting `fields` returns the full GraphQL shape — easy to blow context.
- **Rate limits**: respect Open Targets Platform throttling; enable `OPEN_TARGETS_RATE_LIMIT_RPS` for high-volume jobs.
- Variant tools require canonical OT variant IDs (e.g. `1_55039839_C_T`); resolve via `search_entities` or `get_variant_info` upstream.

## Source layout
- `src/opentargets_mcp/server.py` — FastMCP entrypoint
- `src/opentargets_mcp/tools/` — tool implementations grouped by domain
- `src/opentargets_mcp/queries.py` — GraphQL query strings
- `src/opentargets_mcp/resolver.py` — name → ID resolution
- `src/opentargets_mcp/settings.py` — typed env config

## Dev
```bash
uv run ruff check src tests
uv run pytest tests/ -v
```

## When editing tools
1. Add or modify GraphQL in `queries.py`.
2. Wrap in a tool under `src/opentargets_mcp/tools/<domain>.py`; expose via the registry.
3. Update `--list-tools` count in README if the catalog grows.
4. Add a unit test mocking the GraphQL response.

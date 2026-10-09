# Open Targets MCP Server

[![CI](https://img.shields.io/github/actions/workflow/status/nickzren/opentargets-mcp/ci.yml?label=CI)](https://github.com/nickzren/opentargets-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/opentargets-mcp)](https://pypi.org/project/opentargets-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue)](https://registry.modelcontextprotocol.io/v0/servers?search=nickzren/opentargets&version=latest)
[![License: MIT](https://img.shields.io/github/license/nickzren/opentargets-mcp)](https://github.com/nickzren/opentargets-mcp/blob/main/LICENSE)

An MCP server that lets AI assistants query the [Open Targets Platform](https://platform.opentargets.org/): targets, diseases, drugs, variants, studies and the evidence that links them.

<!-- mcp-name: io.github.nickzren/opentargets -->

## Install

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

**Claude Code**
```bash
claude mcp add opentargets -- uvx opentargets-mcp
```

**Claude Desktop and Cursor**: add this to `claude_desktop_config.json` (Settings → Developer → Edit Config) or `~/.cursor/mcp.json`, then restart:
```json
{
  "mcpServers": {
    "opentargets": {
      "command": "uvx",
      "args": ["opentargets-mcp"]
    }
  }
}
```

**VS Code**
```bash
code --add-mcp '{"name":"opentargets","command":"uvx","args":["opentargets-mcp"]}'
```

**Codex**
```bash
codex mcp add opentargets -- uvx opentargets-mcp
```

Any other stdio MCP client works the same way: command `uvx`, argument `opentargets-mcp`.

Tips: if the client reports `spawn uvx ENOENT`, use the full path from `which uvx`. Use `opentargets-mcp@latest` as the argument to pick up new releases.

## What you can ask

- "Which drugs target EGFR, and how far along are they?"
- "Which genes are most strongly associated with asthma?"
- "Show the evidence linking BRAF to melanoma."
- "Suggest drug repurposing candidates for type 2 diabetes."

Use names or IDs: gene symbols, disease and drug names, rsIDs, or Ensembl, MONDO and ChEMBL IDs. If a name matches several entities, the tool lists the candidates so you can pick one.

## Tools

68 tools. Run `uvx opentargets-mcp --list-tools` for the full list.

| Area | Examples |
|---|---|
| Targets (20) | `get_target_info`, `get_target_associated_diseases`, `get_target_known_drugs`, `get_target_tractability`, `get_target_safety_information` |
| Diseases (8) | `get_disease_info`, `get_disease_associated_targets`, `get_disease_known_drugs`, `get_disease_phenotypes` |
| Drugs (10) | `get_drug_info`, `get_drug_linked_diseases`, `get_drug_adverse_events`, `get_drug_warnings` |
| Evidence (2) | `get_target_disease_evidence`, `get_target_disease_biomarkers` |
| Variants and studies (12) | `get_variant_info`, `get_credible_sets`, `get_study_info`, `get_studies_by_disease` |
| Search and lookup (12) | `search_entities`, `map_ids`, `get_targets_batch`, `get_drugs_batch` |
| Workflow (1) | `get_drug_repurposing_candidates` |
| Raw GraphQL (3) | `graphql_query`, `graphql_batch_query`, `graphql_schema` |

Many tools accept `fields` (dot-paths such as `["target.approvedSymbol"]`) to return only what you need. For anything the curated tools don't cover, use `graphql_query`.

## Configuration

The defaults work for local use. To change them, set environment variables or pass flags (`opentargets-mcp --help`):

| Variable | Flag | Default |
|---|---|---|
| `MCP_TRANSPORT` | `--transport` | `stdio` (also `http`, `sse`) |
| `FASTMCP_SERVER_HOST` | `--host` | `0.0.0.0` |
| `FASTMCP_SERVER_PORT` | `--port` | `8000` |
| `OPEN_TARGETS_API_URL` | `--api` | `https://api.platform.opentargets.org/api/v4/graphql` |
| `OPEN_TARGETS_RATE_LIMIT_RPS` | `--rate-limit-rps` | `0` (off); limits incoming MCP requests |
| `OPEN_TARGETS_RATE_LIMIT_BURST` | `--rate-limit-burst` | `20` |

Proxies are read from `HTTPS_PROXY`, `HTTP_PROXY` and `NO_PROXY`.

## Self-host

From source:
```bash
git clone https://github.com/nickzren/opentargets-mcp
cd opentargets-mcp
uv run opentargets-mcp
```

With Docker (HTTP on port 8000), from the clone:
```bash
docker compose up -d --build
```

## Development

```bash
uv sync --extra dev
uv run ruff check src tests
uv run pytest -m "not live"   # offline
uv run pytest -m live         # calls the Open Targets API
```

Example scripts are in [`examples/`](https://github.com/nickzren/opentargets-mcp/tree/main/examples).

## License

[MIT](https://github.com/nickzren/opentargets-mcp/blob/main/LICENSE)

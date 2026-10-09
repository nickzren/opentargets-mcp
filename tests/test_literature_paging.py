"""Offline paging tests for the literature occurrence tools.

Upstream takes no page size: each cursor advances one full page (25 rows).
Trimming a page to `size` therefore skipped the trimmed rows forever, so
`size` is ignored and every row must be reachable exactly once.
"""

import pytest

from opentargets_mcp.tools.disease import DiseaseApi
from opentargets_mcp.tools.drug import DrugApi
from opentargets_mcp.tools.target import TargetApi

PAGES = {
    None: ([str(pmid) for pmid in range(1, 26)], "page-2"),
    "page-2": ([str(pmid) for pmid in range(26, 31)], None),
}

TOOLS = [
    (TargetApi().get_target_literature_occurrences, "target", "ENSG00000157764"),
    (DiseaseApi().get_disease_literature_occurrences, "disease", "MONDO_0005105"),
    (DrugApi().get_drug_literature_occurrences, "drug", "CHEMBL1229517"),
]


class _PagedClient:
    def __init__(self, entity_key):
        self.entity_key = entity_key
        self.variables = []

    async def _query(self, _query, variables=None):
        self.variables.append(variables or {})
        pmids, cursor = PAGES[(variables or {}).get("cursor")]
        return {
            self.entity_key: {
                "literatureOcurrences": {
                    "count": 30,
                    "cursor": cursor,
                    "rows": [{"pmid": pmid} for pmid in pmids],
                }
            }
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("tool, entity_key, entity_id", TOOLS)
@pytest.mark.parametrize("size_kwargs", [{}, {"size": 20}, {"size": 1}])
async def test_literature_cursor_traversal_sees_every_row_once(
    tool, entity_key, entity_id, size_kwargs
):
    client = _PagedClient(entity_key)
    seen = []
    cursor = None
    while True:
        result = await tool(client, entity_id, cursor=cursor, **size_kwargs)
        literature = result[entity_key]["literatureOcurrences"]
        seen.extend(row["pmid"] for row in literature["rows"])
        cursor = literature["cursor"]
        if cursor is None:
            break

    assert seen == [str(pmid) for pmid in range(1, 31)]
    assert all("size" not in variables for variables in client.variables)

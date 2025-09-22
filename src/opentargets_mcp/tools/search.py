# src/opentargets_mcp/tools/search.py
"""
Defines API methods and MCP tools related to general search functionalities
across multiple entity types in Open Targets.
"""
from typing import Any, Dict, List, Optional
import asyncio
from ..queries import OpenTargetsClient
from .meta import MetaApi

try:
    from thefuzz import process as fuzzy_process
except ImportError:
    fuzzy_process = None


class SearchApi:
    """
    Contains methods for searching entities with intelligent resolution,
    autocomplete, and other search-related functionalities.
    """
    def __init__(self):
        self.meta_api = MetaApi()
        self.fuzzy_process = fuzzy_process
        if not self.fuzzy_process:
            print("Warning: 'thefuzz' library not found. Suggestions will not work. Please install it with 'pip install thefuzz python-Levenshtein'.")

    async def _search_direct(
        self,
        client: OpenTargetsClient,
        query_string: str,
        entity_names: Optional[List[str]],
        page_index: int,
        page_size: int
    ) -> Dict[str, Any]:
        """A private helper method for a direct, simple search."""
        graphql_query = """
        query SearchEntities($queryString: String!, $entityNames: [String!], $pageIndex: Int!, $pageSize: Int!) {
            search(
                queryString: $queryString,
                entityNames: $entityNames,
                page: {index: $pageIndex, size: $pageSize}
            ) {
                total
                hits {
                    id
                    entity
                    name
                    description
                    score
                    highlights
                    object {
                        __typename
                        ... on Target { id, approvedSymbol, approvedName, biotype }
                        ... on Disease { id, name, description, therapeuticAreas { id, name } }
                        ... on Drug { id, name, drugType, maximumClinicalTrialPhase, isApproved }
                    }
                }
            }
        }
        """
        variables = {
            "queryString": query_string,
            "entityNames": entity_names if entity_names else ["target", "disease", "drug"],
            "pageIndex": page_index,
            "pageSize": page_size
        }
        return await client._query(graphql_query, variables)

    async def search_entities(
        self,
        client: OpenTargetsClient,
        query_string: str,
        entity_names: Optional[List[str]] = None,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        Searches for entities and intelligently resolves synonyms or misspellings
        to the best canonical entity.
        """
        direct_search_task = asyncio.create_task(
            self._search_direct(client, query_string, entity_names, page_index, page_size)
        )
        map_ids_task = asyncio.create_task(
            self.meta_api.map_ids(client, [query_string], entity_names=entity_names)
        )

        direct_results, mapped_results = await asyncio.gather(direct_search_task, map_ids_task)

        best_mapped_hit = None
        mappings = mapped_results.get("mapIds", {}).get("mappings", [])
        if mappings and mappings[0].get("hits"):
            best_mapped_hit = max(mappings[0]["hits"], key=lambda hit: hit.get('score', 0), default=None)

        direct_top_hit_id = direct_results.get("search", {}).get("hits", [{}])[0].get("id")
        if best_mapped_hit and best_mapped_hit.get("id") != direct_top_hit_id:
            print(f"Resolving '{query_string}' to best match: '{best_mapped_hit.get('name')}' ({best_mapped_hit.get('id')}). Fetching canonical results.")
            return await self._search_direct(client, best_mapped_hit["id"], entity_names, page_index, page_size)

        return direct_results

    async def search_suggestions(
        self,
        client: OpenTargetsClient,
        query_prefix: str,
        entity_names: Optional[List[str]] = None,
        max_suggestions: int = 10
    ) -> Dict[str, Any]:
        """
        Get autocomplete suggestions for a partial query.
        """
        if not self.fuzzy_process:
            return {"error": "'thefuzz' library is required for suggestions."}
        
        if len(query_prefix) < 3:
            return {"suggestions": [], "message": "Query prefix must be at least 3 characters long."}

        candidates_result = await self._search_direct(
            client,
            query_string=query_prefix,
            entity_names=entity_names,
            page_index=0,
            page_size=50
        )
        
        if not candidates_result or not candidates_result.get("search", {}).get("hits"):
            return {"suggestions": []}

        choices = {}
        for hit in candidates_result["search"]["hits"]:
            name = hit.get("name")
            symbol = hit.get("object", {}).get("approvedSymbol")
            if name and name not in choices:
                choices[name] = {"id": hit["id"], "entity": hit["entity"]}
            if symbol and symbol not in choices:
                choices[symbol] = {"id": hit["id"], "entity": hit["entity"]}
        
        extracted_suggestions = self.fuzzy_process.extractBests(
            query_prefix,
            choices.keys(),
            score_cutoff=70,
            limit=max_suggestions
        )

        suggestions = [
            {
                "label": suggestion[0],
                "score": suggestion[1],
                "id": choices[suggestion[0]]["id"],
                "entity": choices[suggestion[0]]["entity"]
            }
            for suggestion in extracted_suggestions
        ]
        
        return {"suggestions": suggestions}

    async def get_similar_targets(
        self,
        client: OpenTargetsClient,
        entity_id: str,
        threshold: Optional[float] = 0.5,
        size: int = 10
    ) -> Dict[str, Any]:
        """
        Get targets similar to a given target Ensembl ID based on shared associations.
        """
        graphql_query_target = """
        query SimilarTargets($entityId: String!, $threshold: Float, $size: Int!) {
            target(ensemblId: $entityId) {
                id
                approvedSymbol
                similarEntities(threshold: $threshold, size: $size) {
                    score
                    object {
                        __typename
                        ... on Target { id, approvedSymbol, approvedName }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query_target, {"entityId": entity_id, "threshold": threshold, "size": size})

    async def search_facets(
        self,
        client: OpenTargetsClient,
        query_string: Optional[str] = None,
        category_id: Optional[str] = None,
        entity_names: Optional[List[str]] = None,
        page_index: int = 0,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get search facets for filtering, optionally based on a query string."""
        if not query_string:
            query_string = "*"

        graphql_query = """
        query SearchFacets(
            $queryString: String!, $categoryId: String, $entityNames: [String!], $pageIndex: Int!, $pageSize: Int!
        ) {
            facets(
                queryString: $queryString, category: $categoryId, entityNames: $entityNames, page: {index: $pageIndex, size: $pageSize}
            ) {
                total
                categories { name, total }
                hits { id, label, category, score, entityIds, datasourceId, highlights }
            }
        }
        """
        variables = {
            "queryString": query_string,
            "categoryId": category_id,
            "entityNames": entity_names if entity_names else ["target", "disease", "drug"],
            "pageIndex": page_index,
            "pageSize": page_size
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

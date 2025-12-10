# src/opentargets_mcp/tools/search.py
"""
Defines API methods and MCP tools related to general search functionalities
across multiple entity types in Open Targets.
"""
from typing import Any, Dict, List, Optional
import asyncio
import logging
from ..queries import OpenTargetsClient
from ..utils import filter_none_values
from .meta import MetaApi

logger = logging.getLogger(__name__)

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
            logger.warning("'thefuzz' library not found. Suggestions will not work. Please install it with 'pip install thefuzz python-Levenshtein'.")

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
                        ... on Variant { id, chromosome, position, rsIds }
                        ... on Study { id, studyType, traitFromSource }
                    }
                }
            }
        }
        """
        variables = {
            "queryString": query_string,
            "entityNames": entity_names if entity_names else ["target", "disease", "drug", "variant", "study"],
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
        """Search Open Targets entities and resolve synonyms to canonical IDs.

        **When to use**
        - Start any workflow that begins with a free-text gene, disease, or compound query
        - Convert common synonyms (for example, `\"ERBB1\"`) into platform identifiers (`\"ENSG...\"`)
        - Retrieve paginated ranked hits with confidence scores for UI display

        **When not to use**
        - You already know the exact entity identifier (call the domain tool directly)
        - You need autocomplete suggestions while the user types (use `search_suggestions`)
        - You want aggregated facet counts only (use `search_facets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): Configured GraphQL client.
        - `query_string` (`str`): Free-text term such as `"BRAF"` or `"melanoma"`.
        - `entity_names` (`Optional[List[str]]`): Restrict the search to `["target"]`, `["disease"]`, `["drug"]`, or any combination; defaults to all.
        - `page_index` (`int`): Zero-based page to return; use for pagination in large result sets.
        - `page_size` (`int`): Number of hits per page (1–20 recommended; hard limit 100).

        **Returns**
        - `Dict[str, Any]`: Response structured as `{"search": {"total": int, "hits": [{"id": str, "entity": str, "name": str, "score": float, "object": {...}}, ...]}}`.

        **Errors**
        - Bubbles up GraphQL or network exceptions from `OpenTargetsClient`.

        **Example**
        ```python
        search_api = SearchApi()
        result = await search_api.search_entities(client, "BRAF", entity_names=["target"])
        top_hit = result["search"]["hits"][0]
        logger.info("%s %s", top_hit["id"], top_hit["object"]["approvedSymbol"])
        ```
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
            logger.info("Resolving '%s' to best match: '%s' (%s). Fetching canonical results.",
                       query_string, best_mapped_hit.get('name'), best_mapped_hit.get('id'))
            return await self._search_direct(client, best_mapped_hit["id"], entity_names, page_index, page_size)

        return direct_results

    async def search_suggestions(
        self,
        client: OpenTargetsClient,
        query_prefix: str,
        entity_names: Optional[List[str]] = None,
        max_suggestions: int = 10
    ) -> Dict[str, Any]:
        """Return autocomplete suggestions for partially typed queries.

        **When to use**
        - Offer live search hints in conversational or UI agents
        - Pre-validate user input before issuing a full search
        - Guide users toward canonical spellings while they type

        **When not to use**
        - Fuzzy searching across the full corpus (use `search_entities`)
        - Operating in environments without the optional `thefuzz` dependency

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client used to fetch candidate hits.
        - `query_prefix` (`str`): Partial term with at least three characters.
        - `entity_names` (`Optional[List[str]]`): Limit suggestions to specific entity types; defaults to all.
        - `max_suggestions` (`int`): Maximum number of entries to return (default 10).

        **Returns**
        - `Dict[str, Any]`: Either `{"suggestions": [{"label": str, "score": int, "id": str, "entity": str}, ...]}` or an error dictionary when fuzzy matching is unavailable.

        **Errors**
        - Returns `{"error": "...requires thefuzz..."}` if the optional dependency is missing.
        - Propagates client/network exceptions triggered during the candidate search.

        **Example**
        ```python
        search_api = SearchApi()
        suggestions = await search_api.search_suggestions(client, "mel", entity_names=["disease"])
        logger.info([item["label"] for item in suggestions["suggestions"]])
        ```
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
        """Identify targets with similar association profiles to the seed target.

        **When to use**
        - Expand a target list by finding genes with overlapping disease or evidence profiles
        - Prioritise follow-up genes in pathway or clustering analyses
        - Provide recommendations when a user is exploring alternatives to a known target

        **When not to use**
        - Looking for disease-associated targets directly (use `get_target_associated_diseases`)
        - Comparing expression or biology features (use the respective target biology tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `entity_id` (`str`): Ensembl gene identifier (`"ENSG..."`) for the reference target.
        - `threshold` (`Optional[float]`): Minimum similarity score (0–1) to include; defaults to `0.5`.
        - `size` (`int`): Maximum number of similar targets to return (default 10).

        **Returns**
        - `Dict[str, Any]`: GraphQL payload `{"target": {"id": str, "approvedSymbol": str, "similarEntities": [{"score": float, "object": {...}}]}}`.

        **Errors**
        - Raises GraphQL/network exceptions from `OpenTargetsClient` if the query fails.

        **Example**
        ```python
        search_api = SearchApi()
        similar = await search_api.get_similar_targets(client, "ENSG00000157764", threshold=0.6)
        logger.info([hit["object"]["approvedSymbol"] for hit in similar["target"]["similarEntities"]])
        ```
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
        """Return facet counts to help filter search results.

        **When to use**
        - Build dynamic filters (by datasource, entity type, etc.) before issuing detailed queries
        - Provide an overview of the distribution of results for a given search term
        - Support UI components that need to know which categories have content

        **When not to use**
        - Fetching individual search hits (use `search_entities`)
        - Needing aggregation beyond the built-in facet categories

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `query_string` (`Optional[str]`): Free-text term; defaults to `"*"` (all records) when omitted.
        - `category_id` (`Optional[str]`): Restrict facets to a particular category (for example `"datasource"`).
        - `entity_names` (`Optional[List[str]]`): Limit the facet calculation to specific entity types.
        - `page_index` (`int`): Zero-based index for paging facet hits.
        - `page_size` (`int`): Number of facet hits to return (default 20; capped by API).

        **Returns**
        - `Dict[str, Any]`: Response `{"facets": {"total": int, "categories": [{"name": str, "total": int}, ...], "hits": [...]}}`.

        **Errors**
        - GraphQL or network failures propagate from the client.

        **Example**
        ```python
        search_api = SearchApi()
        facets = await search_api.search_facets(client, query_string="BRAF")
        logger.info(facets["facets"]["categories"])
        ```
        """
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
        variables = filter_none_values({
            "queryString": query_string,
            "categoryId": category_id,
            "entityNames": entity_names if entity_names else ["target", "disease", "drug", "variant", "study"],
            "pageIndex": page_index,
            "pageSize": page_size
        })
        return await client._query(graphql_query, variables)

# src/opentargets_mcp/tools/search.py
"""
Defines API methods and MCP tools related to general search functionalities
across multiple entity types in Open Targets.
"""
from typing import Any, Dict, List, Optional
import mcp.types as types
from ..queries import OpenTargetsClient # Relative import

class SearchApi:
    """
    Contains methods for searching across entities and other search-related queries.
    """

    async def search_entities(
        self,
        client: OpenTargetsClient,
        query_string: str,
        entity_names: Optional[List[str]] = None, 
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Search across multiple entity types (targets, diseases, drugs) using a query string."""
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
                        ... on Target {
                            id, approvedSymbol, approvedName, biotype
                        }
                        ... on Disease {
                            id, name, description, therapeuticAreas { id, name }
                        }
                        ... on Drug {
                            id, name, drugType, maximumClinicalTrialPhase, isApproved
                        }
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

    async def get_similar_targets( # Method name confirmed/corrected
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
                similarEntities(threshold: $threshold, size: $size) { # GraphQL field name is similarEntities
                    score 
                    # 'type' field removed as API reported: "Cannot query field 'type' on type 'Similarity'"
                    # The type can be inferred from the __typename of the object or which fragment matches.
                    object {
                        __typename # Request __typename to help identify the object's type
                        ... on Target { 
                            id
                            approvedSymbol
                            approvedName 
                        }
                        # Add fragments for Disease or Drug if cross-entity similarity is expected and supported
                        # ... on Disease { id, name }
                        # ... on Drug { id, name }
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
            $queryString: String!,
            $categoryId: String, 
            $entityNames: [String!],
            $pageIndex: Int!,
            $pageSize: Int!
        ) {
            facets(
                queryString: $queryString,
                category: $categoryId,
                entityNames: $entityNames,
                page: {index: $pageIndex, size: $pageSize}
            ) {
                total 
                categories { 
                    name
                    total
                }
                hits { 
                    id
                    label
                    category
                    score
                    entityIds 
                    datasourceId
                    highlights
                }
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


SEARCH_TOOLS = [
    types.Tool(
        name="search_entities",
        description="Search across multiple entity types (targets, diseases, drugs) using a query string.",
        inputSchema={
            "type": "object",
            "properties": {
                "query_string": {"type": "string", "description": "The search term or query string."},
                "entity_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of entity types to search (e.g., ['target', 'disease']). Defaults to all."
                },
                "page_index": {"type": "number", "description": "Page number for results (default: 0).", "default": 0},
                "page_size": {"type": "number", "description": "Number of results per page (default: 10).", "default": 10}
            },
            "required": ["query_string"]
        }
    ),
    types.Tool(
        name="get_similar_targets", 
        description="Get targets similar to a given target Ensembl ID based on shared associations.",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "Ensembl ID of the target to find similar entities for."},
                "threshold": {"type": "number", "description": "Minimum similarity score (0.0 to 1.0). Optional, defaults to 0.5.", "default": 0.5},
                "size": {"type": "number", "description": "Number of similar entities to return (default: 10).", "default": 10}
            },
            "required": ["entity_id"]
        }
    ),
    types.Tool(
        name="search_facets",
        description="Get search facets (aggregations/filters) based on an optional query string and entity types. Useful for building filter UIs.",
        inputSchema={
            "type": "object",
            "properties": {
                "query_string": {"type": "string", "description": "Optional query string to base facets on. Use '*' for broad facets."},
                "category_id": {"type": "string", "description": "Specific facet category to retrieve (e.g., 'datasource', 'therapeutic_area'). Optional."},
                "entity_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of entity types to consider for facets (e.g., ['target', 'disease']). Defaults to all."
                },
                "page_index": {"type": "number", "description": "Page number for facet hits (default: 0).", "default": 0},
                "page_size": {"type": "number", "description": "Number of facet hits per page (default: 20).", "default": 20}
            },
            "required": [] 
        }
    )
]

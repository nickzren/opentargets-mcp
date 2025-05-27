# src/opentargets_mcp/tools/meta.py
"""
Defines API methods and MCP tools for metadata and utility functions in Open Targets.
"""
from typing import Any, Dict, List, Optional
import mcp.types as types
from ..queries import OpenTargetsClient

class MetaApi:
    """
    Contains methods for metadata and utility queries.
    """

    async def get_api_metadata(self, client: OpenTargetsClient) -> Dict[str, Any]:
        """Get API version and data version information."""
        graphql_query = """
        query ApiMetadata {
            meta {
                name
                apiVersion {
                    x
                    y
                    z
                }
                dataVersion {
                    year
                    month
                    iteration
                }
            }
        }
        """
        return await client._query(graphql_query)

    async def get_association_datasources(self, client: OpenTargetsClient) -> Dict[str, Any]:
        """Get list of all available datasources for associations."""
        graphql_query = """
        query AssociationDatasources {
            associationDatasources {
                datasource
                datatype
            }
        }
        """
        return await client._query(graphql_query)

    async def get_interaction_resources(self, client: OpenTargetsClient) -> Dict[str, Any]:
        """Get list of all available interaction resources."""
        graphql_query = """
        query InteractionResources {
            interactionResources {
                sourceDatabase
                databaseVersion
            }
        }
        """
        return await client._query(graphql_query)

    async def get_gene_ontology_terms(self, client: OpenTargetsClient, go_ids: List[str]) -> Dict[str, Any]:
        """Get Gene Ontology term information by GO IDs."""
        graphql_query = """
        query GeneOntologyTerms($goIds: [String!]!) {
            geneOntologyTerms(goIds: $goIds) {
                id
                name
            }
        }
        """
        return await client._query(graphql_query, {"goIds": go_ids})

    async def map_ids(
        self,
        client: OpenTargetsClient,
        query_terms: List[str],
        entity_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Map free text terms to Open Targets IDs."""
        graphql_query = """
        query MapIds($queryTerms: [String!]!, $entityNames: [String!]) {
            mapIds(queryTerms: $queryTerms, entityNames: $entityNames) {
                total
                mappings {
                    term
                    hits {
                        id
                        name
                        entity
                        category
                        multiplier
                        prefixes
                        score
                        object {
                            __typename
                            ... on Target {
                                id
                                approvedSymbol
                                approvedName
                            }
                            ... on Disease {
                                id
                                name
                                description
                            }
                            ... on Drug {
                                id
                                name
                                drugType
                            }
                        }
                    }
                }
                aggregations {
                    total
                    entities {
                        name
                        total
                        categories {
                            name
                            total
                        }
                    }
                }
            }
        }
        """
        variables = {
            "queryTerms": query_terms,
            "entityNames": entity_names if entity_names else ["target", "disease", "drug"]
        }
        return await client._query(graphql_query, variables)


META_TOOLS = [
    types.Tool(
        name="get_api_metadata",
        description="Get Open Targets Platform API version and data version information.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    types.Tool(
        name="get_association_datasources",
        description="Get list of all available datasources used for target-disease associations.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    types.Tool(
        name="get_interaction_resources",
        description="Get list of all available protein-protein interaction databases.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    types.Tool(
        name="get_gene_ontology_terms",
        description="Get Gene Ontology (GO) term information by GO IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "go_ids": {"type": "array", "items": {"type": "string"}, "description": "List of GO IDs (e.g., ['GO:0005515', 'GO:0008270'])."}
            },
            "required": ["go_ids"]
        }
    ),
    types.Tool(
        name="map_ids",
        description="Map free text terms to Open Targets IDs. Useful for converting gene symbols, disease names, or drug names to their respective IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "query_terms": {"type": "array", "items": {"type": "string"}, "description": "List of terms to map (e.g., ['BRAF', 'melanoma', 'vemurafenib'])."},
                "entity_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter results by entity types (e.g., ['target', 'disease', 'drug']). Defaults to all."
                }
            },
            "required": ["query_terms"]
        }
    )
]

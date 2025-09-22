# src/opentargets_mcp/tools/meta.py
"""
Defines API methods and MCP tools for metadata and utility functions in Open Targets.
"""
from typing import Any, Dict, List, Optional
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


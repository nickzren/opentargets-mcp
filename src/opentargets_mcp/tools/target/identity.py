# src/opentargets_mcp/tools/target/identity.py
"""
Defines API methods and MCP tools related to a target's identity and classification.
"""
from typing import Any, Dict
from ...queries import OpenTargetsClient

class TargetIdentityApi:
    """
    Contains methods to query a target's identity, classification, and cross-references.
    """
    async def get_target_info(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific target by its Ensembl ID."""
        graphql_query = """
        query TargetInfo($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                approvedName
                biotype
                functionDescriptions
                synonyms { label, source }
                genomicLocation { chromosome, start, end, strand }
                proteinIds { id, source }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_class(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get target class information from ChEMBL."""
        graphql_query = """
        query TargetClass($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                targetClass {
                    id
                    label
                    level
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_alternative_genes(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get alternative genes and database cross-references for a target."""
        graphql_query = """
        query TargetAlternativeGenes($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                alternativeGenes
                transcriptIds
                dbXrefs {
                    id
                    source
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

# src/opentargets_mcp/tools/drug/associations.py
"""
Defines API methods and MCP tools related to a drug's associations with other entities.
"""
from typing import Any, Dict
from ...queries import OpenTargetsClient

class DrugAssociationsApi:
    """
    Contains methods to query a drug's associations with diseases and targets.
    """
    async def get_drug_linked_diseases(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """Get all diseases linked to a drug through clinical trials or mechanisms."""
        graphql_query = """
        query DrugLinkedDiseases($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                linkedDiseases {
                    count
                    rows {
                        id
                        name
                        description
                        therapeuticAreas {
                            id
                            name
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})

    async def get_drug_linked_targets(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """Get all targets linked to a drug based on mechanism of action."""
        graphql_query = """
        query DrugLinkedTargets($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                linkedTargets {
                    count
                    rows {
                        id
                        approvedSymbol
                        approvedName
                        biotype
                        proteinIds {
                            id
                            source
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})

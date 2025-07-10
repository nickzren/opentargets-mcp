# src/opentargets_mcp/tools/drug/identity.py
"""
Defines API methods and MCP tools related to a drug's identity and classification.
"""
from typing import Any, Dict
import mcp.types as types
from ...queries import OpenTargetsClient

class DrugIdentityApi:
    """
    Contains methods to query a drug's identity and cross-references.
    """
    async def get_drug_info(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific drug by its ChEMBL ID."""
        graphql_query = """
        query DrugInfo($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                synonyms
                tradeNames
                drugType
                description
                isApproved
                hasBeenWithdrawn
                blackBoxWarning
                yearOfFirstApproval
                maximumClinicalTrialPhase
                mechanismsOfAction {
                    rows {
                       mechanismOfAction
                       targetName
                       targets {
                           id
                           approvedSymbol
                       }
                       actionType
                       references {
                           source
                           ids
                           urls
                       }
                    }
                }
                indications {
                    rows {
                        disease {
                            id
                            name
                            therapeuticAreas {id, name}
                        }
                        maxPhaseForIndication
                        references {
                            source
                            ids
                        }
                    }
                    count
                }
                linkedTargets {
                    rows {
                        id
                        approvedSymbol
                        biotype
                    }
                    count
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})

    async def get_drug_cross_references(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """Get cross-references to other databases for a drug."""
        graphql_query = """
        query DrugCrossReferences($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                synonyms
                crossReferences {
                    source
                    ids
                }
                parentMolecule {
                    id
                    name
                }
                childMolecules {
                    id
                    name
                    drugType
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})

DRUG_IDENTITY_TOOLS = [
    types.Tool(
        name="get_drug_info",
        description="Get detailed information about a specific drug by its ChEMBL ID (e.g., CHEMBL1201583 for Vemurafenib). Includes mechanism of action, indications, and clinical trial phase.",
        inputSchema={
            "type": "object",
            "properties": {"chembl_id": {"type": "string", "description": "ChEMBL ID of the drug."}},
            "required": ["chembl_id"]
        }
    ),
    types.Tool(
        name="get_drug_cross_references",
        description="Get cross-references to other databases and parent/child molecule relationships.",
        inputSchema={
            "type": "object",
            "properties": {"chembl_id": {"type": "string", "description": "ChEMBL ID of the drug."}},
            "required": ["chembl_id"]
        }
    ),
]
# src/opentargets_mcp/tools/drug.py
"""
Defines API methods and MCP tools related to 'Drug' entities in Open Targets.
"""
from typing import Any, Dict, Optional
import mcp.types as types
from ..queries import OpenTargetsClient # Relative import

class DrugApi:
    """
    Contains methods to query drug-specific data from the Open Targets GraphQL API.
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
                mechanismsOfAction { # PaginatedMechanismsOfAction - API schema shows this is not paginated directly here.
                    rows { # MechanismOfActionRow
                       mechanismOfAction
                       targetName 
                       targets { # Target
                           id
                           approvedSymbol
                       }
                       actionType
                       references { # Publication
                           source
                           ids
                           urls
                       }
                    }
                    # count # Not available on mechanismsOfAction directly
                }
                indications { # Removed 'page' argument as it's not supported for this field
                    rows { # IndicationRow
                        disease { # Disease
                            id
                            name
                            therapeuticAreas {id, name}
                        }
                        maxPhaseForIndication
                        references { # Publication
                            source
                            ids
                        }
                    }
                    count # Count is available on IndicationConnection
                }
                linkedTargets { # LinkedTargetConnection
                    rows { # Target
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

    async def get_drug_adverse_events(self, client: OpenTargetsClient, chembl_id: str, page_index: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """Get adverse event information for a drug from FAERS and MedDRA."""
        graphql_query = """
        query DrugAdverseEvents($chemblId: String!, $pageIndex: Int!, $pageSize: Int!) {
            drug(chemblId: $chemblId) {
                id
                name
                adverseEvents(page: {index: $pageIndex, size: $pageSize}) { # PaginatedAdverseEvents
                    count
                    criticalValue 
                    rows { # AdverseEvent
                        meddraCode
                        name # Corrected from 'term' to 'name' for MedDRA term
                        count 
                        logLR 
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id, "pageIndex": page_index, "pageSize": page_size})
    
    async def get_drug_pharmacovigilance(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """
        Get pharmacovigilance data for a drug, including adverse events and withdrawal information.
        """
        graphql_query = """
        query DrugPharmacovigilance($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                isApproved
                hasBeenWithdrawn
                blackBoxWarning
                adverseEvents(page: {index: 0, size: 20}) { # Sample of AEs
                     count
                     criticalValue
                     rows { 
                         meddraCode, 
                         name, # Corrected from 'term' to 'name'
                         count, 
                         logLR 
                     }
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})


DRUG_TOOLS = [
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
        name="get_drug_adverse_events",
        description="Get adverse event information for a drug from FAERS and MedDRA.",
        inputSchema={
            "type": "object",
            "properties": {
                "chembl_id": {"type": "string", "description": "ChEMBL ID of the drug."},
                "page_index": {"type": "number", "description": "Page number for results (default: 0).", "default": 0},
                "page_size": {"type": "number", "description": "Number of results per page (default: 10).", "default": 10}
            },
            "required": ["chembl_id"]
        }
    ),
    types.Tool(
        name="get_drug_pharmacovigilance",
        description="Get pharmacovigilance data for a drug, including adverse events and withdrawal information.",
         inputSchema={
            "type": "object",
            "properties": {"chembl_id": {"type": "string", "description": "ChEMBL ID of the drug."}},
            "required": ["chembl_id"]
        }
    )
]

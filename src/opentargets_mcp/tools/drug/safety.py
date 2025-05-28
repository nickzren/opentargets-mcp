# src/opentargets_mcp/tools/drug/safety.py
"""
Defines API methods and MCP tools related to drug safety and pharmacovigilance.
"""
from typing import Any, Dict
import mcp.types as types
from ...queries import OpenTargetsClient

class DrugSafetyApi:
    """
    Contains methods to query drug safety, warnings, and adverse events.
    """
    async def get_drug_adverse_events(self, client: OpenTargetsClient, chembl_id: str, page_index: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """Get adverse event information for a drug from FAERS and MedDRA."""
        graphql_query = """
        query DrugAdverseEvents($chemblId: String!, $pageIndex: Int!, $pageSize: Int!) {
            drug(chemblId: $chemblId) {
                id
                name
                adverseEvents(page: {index: $pageIndex, size: $pageSize}) {
                    count
                    criticalValue
                    rows {
                        meddraCode
                        name
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
                adverseEvents(page: {index: 0, size: 20}) {
                     count
                     criticalValue
                     rows {
                         meddraCode,
                         name,
                         count,
                         logLR
                     }
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})

    async def get_drug_warnings(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """Get detailed drug warnings including withdrawals and black box warnings."""
        graphql_query = """
        query DrugWarnings($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                hasBeenWithdrawn
                blackBoxWarning
                drugWarnings {
                    warningType
                    description
                    toxicityClass
                    country
                    year
                    efoId
                    efoTerm
                    efoIdForWarningClass
                    references {
                        id
                        source
                        url
                    }
                    chemblIds
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})


DRUG_SAFETY_TOOLS = [
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
    ),
    types.Tool(
        name="get_drug_warnings",
        description="Get detailed safety warnings for a drug including withdrawals, black box warnings, and toxicity information.",
        inputSchema={
            "type": "object",
            "properties": {"chembl_id": {"type": "string", "description": "ChEMBL ID of the drug."}},
            "required": ["chembl_id"]
        }
    ),
]
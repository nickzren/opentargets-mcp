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
                    reference
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
    ),
    types.Tool(
        name="get_drug_linked_diseases",
        description="Get all diseases linked to a drug through approved indications or clinical trials.",
        inputSchema={
            "type": "object",
            "properties": {"chembl_id": {"type": "string", "description": "ChEMBL ID of the drug."}},
            "required": ["chembl_id"]
        }
    ),
    types.Tool(
        name="get_drug_linked_targets",
        description="Get all molecular targets linked to a drug based on its mechanism of action.",
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
    types.Tool(
        name="get_drug_cross_references",
        description="Get cross-references to other databases and parent/child molecule relationships.",
        inputSchema={
            "type": "object",
            "properties": {"chembl_id": {"type": "string", "description": "ChEMBL ID of the drug."}},
            "required": ["chembl_id"]
        }
    )
]
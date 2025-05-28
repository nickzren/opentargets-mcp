# src/opentargets_mcp/tools/target/safety.py
"""
Defines API methods and MCP tools related to target safety and tractability.
"""
from typing import Any, Dict
import mcp.types as types
from ...queries import OpenTargetsClient

class TargetSafetyApi:
    """
    Contains methods to query target safety, tractability, and chemical probes.
    """
    async def get_target_safety_information(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get safety liabilities and information for a target."""
        graphql_query = """
        query TargetSafety($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                safetyLiabilities {
                    event
                    eventId
                    effects {
                        direction
                        dosing
                    }
                    datasource
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_tractability(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get tractability assessment for a target, including antibody and small molecule tractability."""
        graphql_query = """
        query TargetTractability($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                tractability {
                    modality
                    value
                    label
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_chemical_probes(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get chemical probes for target validation, including quality scores."""
        graphql_query = """
        query TargetChemicalProbes($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                chemicalProbes {
                    id
                    control
                    drugId
                    isHighQuality
                    mechanismOfAction
                    origin
                    probesDrugsScore
                    probeMinerScore
                    scoreInCells
                    scoreInOrganisms
                    targetFromSourceId
                    urls { niceName, url }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_tep(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get Target Enabling Package (TEP) information for a target."""
        graphql_query = """
        query TargetTEP($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                tep {
                    name
                    therapeuticArea
                    uri
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_prioritization(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get target prioritization scores from various sources."""
        graphql_query = """
        query TargetPrioritisation($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                prioritisation {
                    items {
                        key
                        value
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})


TARGET_SAFETY_TOOLS = [
    types.Tool(
        name="get_target_safety_information",
        description="Get safety liabilities and information for a target.",
        inputSchema={
            "type": "object",
            "properties": {"ensembl_id": {"type": "string", "description": "Ensembl ID of the target."}},
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_tractability",
        description="Get tractability assessment for a target (antibody and small molecule).",
        inputSchema={
            "type": "object",
            "properties": {"ensembl_id": {"type": "string", "description": "Ensembl ID of the target."}},
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_chemical_probes",
        description="Get chemical probes for target validation, including quality scores.",
        inputSchema={
            "type": "object",
            "properties": {"ensembl_id": {"type": "string", "description": "Ensembl ID of the target."}},
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_tep",
        description="Get Target Enabling Package (TEP) information for a target.",
        inputSchema={
            "type": "object",
            "properties": {"ensembl_id": {"type": "string", "description": "Ensembl ID of the target."}},
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_prioritization",
        description="Get target prioritization scores from various sources.",
        inputSchema={
            "type": "object",
            "properties": {"ensembl_id": {"type": "string", "description": "Ensembl ID of the target."}},
            "required": ["ensembl_id"]
        }
    ),
]
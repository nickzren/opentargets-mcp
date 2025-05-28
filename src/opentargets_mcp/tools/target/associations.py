# src/opentargets_mcp/tools/target/associations.py
"""
Defines API methods and MCP tools related to a target's associations.
"""
from typing import Any, Dict, List, Optional
import mcp.types as types
from ...queries import OpenTargetsClient

class TargetAssociationsApi:
    """
    Contains methods to query a target's associations with diseases, drugs, etc.
    """
    async def get_target_associated_diseases(self, client: OpenTargetsClient, ensembl_id: str, page_index: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """Get diseases associated with a target."""
        graphql_query = """
        query TargetAssociatedDiseases($ensemblId: String!, $pageIndex: Int!, $pageSize: Int!) {
            target(ensemblId: $ensemblId) {
                associatedDiseases(page: {index: $pageIndex, size: $pageSize}) {
                    count
                    rows {
                        disease { id, name, description, therapeuticAreas { id, name } }
                        score
                        datatypeScores { id, score }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id, "pageIndex": page_index, "pageSize": page_size})

    async def get_target_known_drugs(self, client: OpenTargetsClient, ensembl_id: str, page_index: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """Get drugs/compounds known to interact with a specific target."""
        graphql_query = """
        query TargetKnownDrugs($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                knownDrugs {
                    count
                    rows {
                        drugId
                        targetId
                        drug {
                            id
                            name
                            drugType
                            maximumClinicalTrialPhase
                            isApproved
                            description
                        }
                        mechanismOfAction
                        disease {
                            id
                            name
                        }
                        phase
                        status
                        urls {
                            name
                            url
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_literature_occurrences(
        self,
        client: OpenTargetsClient,
        ensembl_id: str,
        additional_entity_ids: Optional[List[str]] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        cursor: Optional[str] = None,
        size: int = 20
    ) -> Dict[str, Any]:
        """Get literature co-occurrences for a target, optionally with other entities (diseases, drugs)."""
        graphql_query = """
        query TargetLiteratureOcurrences(
            $ensemblId: String!,
            $additionalIds: [String!],
            $startYear: Int,
            $endYear: Int,
            $cursor: String
        ) {
            target(ensemblId: $ensemblId) {
                literatureOcurrences(
                    additionalIds: $additionalIds,
                    startYear: $startYear,
                    endYear: $endYear,
                    cursor: $cursor
                ) {
                    count
                    cursor
                    rows {
                        pmid
                        pmcid
                        publicationDate
                        sentences {
                            section
                            matches {
                                mappedId
                                matchedLabel
                                matchedType
                                startInSentence
                                endInSentence
                            }
                        }
                    }
                }
            }
        }
        """
        variables = {
            "ensemblId": ensembl_id,
            "additionalIds": additional_entity_ids,
            "startYear": start_year,
            "endYear": end_year,
            "cursor": cursor,
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

TARGET_ASSOCIATIONS_TOOLS = [
    types.Tool(
        name="get_target_associated_diseases",
        description="Get diseases associated with a specific target.",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {"type": "string", "description": "Ensembl ID of the target."},
                "page_index": {"type": "number", "description": "Page number for results (default: 0).", "default": 0},
                "page_size": {"type": "number", "description": "Number of results per page (default: 10).", "default": 10}
            },
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_known_drugs",
        description="Get drugs/compounds known to interact with a specific target.",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {"type": "string", "description": "Ensembl ID of the target."},
                "page_index": {"type": "number", "description": "Page number (default: 0). Not used by API for this endpoint.", "default": 0},
                "page_size": {"type": "number", "description": "Results per page (default: 10). Not used by API for this endpoint.", "default": 10}
            },
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_literature_occurrences",
        description="Get literature co-occurrences for a target, optionally with other entities (diseases, drugs).",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {"type": "string", "description": "Ensembl ID of the target."},
                "additional_entity_ids": {"type": "array", "items": {"type": "string"}, "description": "List of additional entity IDs (EFO for diseases, ChEMBL for drugs) for co-occurrence. Optional."},
                "start_year": {"type": "integer", "description": "Filter by publication start year. Optional."},
                "end_year": {"type": "integer", "description": "Filter by publication end year. Optional."},
                "cursor": {"type": "string", "description": "Cursor for pagination from previous results. Optional."},
                "size": {"type": "integer", "description": "Number of results per page (default: 20). Not used by API for this endpoint.", "default": 20}
            },
            "required": ["ensembl_id"]
        }
    ),
]
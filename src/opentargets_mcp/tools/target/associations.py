# src/opentargets_mcp/tools/target/associations.py
"""
Defines API methods and MCP tools related to a target's associations.
"""
from typing import Any, Dict, List, Optional
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
        start_month: Optional[int] = None,
        end_month: Optional[int] = None,
        cursor: Optional[str] = None,
        size: Optional[int] = 20,
    ) -> Dict[str, Any]:
        """
        Get literature co-occurrences for a target, optionally with other entities.

        The Open Targets API no longer supports server-side pagination for
        ``literatureOcurrences``. When ``size`` is provided, this helper trims the
        returned rows client-side to the requested length.
        """

        graphql_query = """
        query TargetLiteratureOcurrences(
            $ensemblId: String!,
            $additionalIds: [String!],
            $startYear: Int,
            $startMonth: Int,
            $endYear: Int,
            $endMonth: Int,
            $cursor: String
        ) {
            target(ensemblId: $ensemblId) {
                literatureOcurrences(
                    additionalIds: $additionalIds,
                    startYear: $startYear,
                    startMonth: $startMonth,
                    endYear: $endYear,
                    endMonth: $endMonth,
                    cursor: $cursor
                ) {
                    count
                    filteredCount
                    earliestPubYear
                    cursor
                    rows {
                        pmid
                        pmcid
                        publicationDate
                    }
                }
            }
        }
        """

        variables = {
            "ensemblId": ensembl_id,
            "additionalIds": additional_entity_ids,
            "startYear": start_year,
            "startMonth": start_month,
            "endYear": end_year,
            "endMonth": end_month,
            "cursor": cursor,
        }
        variables = {k: v for k, v in variables.items() if v is not None}

        result = await client._query(graphql_query, variables)

        if (
            size is not None
            and isinstance(size, int)
            and size >= 0
            and result.get("target")
        ):
            literature = result["target"].get("literatureOcurrences")
            if literature and isinstance(literature, dict):
                rows = literature.get("rows")
                if isinstance(rows, list):
                    literature["rows"] = rows[:size]

        return result

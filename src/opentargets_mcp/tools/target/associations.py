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
    async def get_target_associated_diseases(
        self,
        client: OpenTargetsClient,
        ensembl_id: str,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """List diseases linked to a target with association scores.

        **When to use**
        - Prioritise therapeutic opportunities for a gene
        - Display paginated association tables with datatype breakdowns
        - Provide context prior to drilling into evidence-level data

        **When not to use**
        - Looking for drug information (use `get_target_known_drugs`)
        - Surfacing literature occurrences (use `get_target_literature_occurrences`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.
        - `page_index` (`int`): Zero-based page (default 0).
        - `page_size` (`int`): Number of disease rows per page (default 10).

        **Returns**
        - `Dict[str, Any]`: `{"target": {"associatedDiseases": {"count": int, "rows": [{"disease": {...}, "score": float, "datatypeScores": [...]}, ...]}}}`.

        **Errors**
        - Propagates GraphQL/network exceptions.

        **Example**
        ```python
        assoc_api = TargetAssociationsApi()
        diseases = await assoc_api.get_target_associated_diseases(client, "ENSG00000157764", page_size=5)
        print(diseases["target"]["associatedDiseases"]["rows"][0]["disease"]["name"])
        ```
        """
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

    async def get_target_known_drugs(
        self,
        client: OpenTargetsClient,
        ensembl_id: str,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Return compounds with known activity on the target.

        **When to use**
        - Inventory approved or investigational drugs acting on a gene
        - Provide clinical phase and approval status in conversational replies
        - Follow up by exploring disease context for each drug–target pair

        **When not to use**
        - Finding targets for a given drug (use drug association tools)
        - Listing diseases without drug context (use `get_target_associated_diseases`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.
        - `page_index` (`int`): Reserved pagination parameter (API returns all known drugs).
        - `page_size` (`int`): Reserved parameter for interface consistency.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"knownDrugs": {"count": int, "rows": [{"drug": {...}, "mechanismOfAction": str, "disease": {...}, "phase": int, "status": str, "urls": [...]}, ...]}}}`.

        **Errors**
        - GraphQL/network exceptions are raised by the client.

        **Example**
        ```python
        assoc_api = TargetAssociationsApi()
        known = await assoc_api.get_target_known_drugs(client, "ENSG00000157764")
        print(known["target"]["knownDrugs"]["rows"][0]["drug"]["name"])
        ```
        """
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
        """Return literature co-occurrence records for a target.

        **When to use**
        - Surface PubMed/Europe PMC references that mention the target
        - Filter by additional entity IDs to find co-mentions (e.g., gene + disease)
        - Provide publication timelines with optional year/month filters

        **When not to use**
        - Retrieving association scores or evidence records (use dedicated tools)
        - Performing full-text search; this operates on curated co-occurrence data

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.
        - `additional_entity_ids` (`Optional[List[str]]`): Optional list of additional entity IDs to co-filter on.
        - `start_year` / `end_year` (`Optional[int]`): Restrict results by publication year.
        - `start_month` / `end_month` (`Optional[int]`): Additional month-level filtering.
        - `cursor` (`Optional[str]`): Pagination cursor provided by API.
        - `size` (`Optional[int]`): Client-side cap on returned rows (since the API no longer paginates server-side).

        **Returns**
        - `Dict[str, Any]`: Response `{"target": {"literatureOcurrences": {"count": int, "filteredCount": int, "earliestPubYear": int, "cursor": str, "rows": [{"pmid": str, "pmcid": str, "publicationDate": str}, ...]}}}` with rows trimmed locally to `size` when provided.

        **Errors**
        - GraphQL/network exceptions surface via the client.

        **Example**
        ```python
        assoc_api = TargetAssociationsApi()
        papers = await assoc_api.get_target_literature_occurrences(
            client, "ENSG00000157764", additional_entity_ids=["EFO_0003884"], size=10
        )
        print(papers["target"]["literatureOcurrences"]["rows"][0]["pmid"])
        ```

        The Open Targets API no longer performs server-side pagination for
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

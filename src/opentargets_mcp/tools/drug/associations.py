# src/opentargets_mcp/tools/drug/associations.py
"""
Defines API methods and MCP tools related to a drug's associations with other entities.
"""
from typing import Any, Dict, List, Optional
from ...queries import OpenTargetsClient
from ...utils import select_fields

class DrugAssociationsApi:
    """
    Contains methods to query a drug's associations with diseases and targets.
    """
    async def get_drug_linked_diseases(
        self,
        client: OpenTargetsClient,
        chembl_id: str,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """List diseases connected to a drug across indications and mechanisms.

        **When to use**
        - Summarise a compound’s therapeutic footprint across disease areas
        - Populate UI components with known disease indications for a drug
        - Provide context before exploring disease-specific evidence

        **When not to use**
        - Retrieving detailed clinical trial evidence (use evidence tools)
        - Discovering drugs for a disease (use disease association tools instead)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `chembl_id` (`str`): Drug identifier.
        - `fields` (`Optional[List[str]]`): Optional dot-paths to filter the response payload.

        **Returns**
        - `Dict[str, Any]`: `{"drug": {"id": str, "name": str, "linkedDiseases": {"count": int, "rows": [{"id": str, "name": str, "therapeuticAreas": [...]}, ...]}}}`.

        **Errors**
        - GraphQL and network failures are surfaced via the client.

        **Example**
        ```python
        drug_api = DrugAssociationsApi()
        diseases = await drug_api.get_drug_linked_diseases(client, "CHEMBL1862")
        print([row["name"] for row in diseases["drug"]["linkedDiseases"]["rows"]])
        ```
        """
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
        result = await client._query(graphql_query, {"chemblId": chembl_id})
        return select_fields(result, fields)

    async def get_drug_linked_targets(
        self,
        client: OpenTargetsClient,
        chembl_id: str,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Return targets linked to a drug via mechanism-of-action data.

        **When to use**
        - Explore which proteins a therapeutic acts upon
        - Prepare target-centric queries (e.g., fetch safety profiles for affected targets)
        - Support mechanism panels or summaries in conversational agents

        **When not to use**
        - Identifying drugs that modulate a specific target (use target association tools)
        - Investigating safety events (use drug safety APIs)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `chembl_id` (`str`): Drug identifier.
        - `fields` (`Optional[List[str]]`): Optional dot-paths to filter the response payload.

        **Returns**
        - `Dict[str, Any]`: `{"drug": {"id": str, "name": str, "linkedTargets": {"count": int, "rows": [{"id": str, "approvedSymbol": str, "approvedName": str, "biotype": str, "proteinIds": [...]}, ...]}}}`.

        **Errors**
        - Propagates GraphQL/network exceptions.

        **Example**
        ```python
        drug_api = DrugAssociationsApi()
        targets = await drug_api.get_drug_linked_targets(client, "CHEMBL1862")
        print([row["approvedSymbol"] for row in targets["drug"]["linkedTargets"]["rows"]])
        ```
        """
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
        result = await client._query(graphql_query, {"chemblId": chembl_id})
        return select_fields(result, fields)

    async def get_drug_literature_occurrences(
        self,
        client: OpenTargetsClient,
        chembl_id: str,
        additional_entity_ids: Optional[List[str]] = None,
        start_year: Optional[int] = None,
        start_month: Optional[int] = None,
        end_year: Optional[int] = None,
        end_month: Optional[int] = None,
        cursor: Optional[str] = None,
        size: Optional[int] = 20,
    ) -> Dict[str, Any]:
        """Return literature co-occurrence records mentioning a drug.

        **When to use**
        - Find publications discussing a specific drug
        - Filter by co-mentioned entities (e.g., drug + disease)
        - Provide publication timelines

        **When not to use**
        - Getting drug mechanisms (use `get_drug_info`)
        - Finding linked diseases (use `get_drug_linked_diseases`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `chembl_id` (`str`): Drug identifier.
        - `additional_entity_ids` (`Optional[List[str]]`): Co-filter entities.
        - `start_year` / `end_year` (`Optional[int]`): Year filters.
        - `start_month` / `end_month` (`Optional[int]`): Month filters.
        - `cursor` (`Optional[str]`): Pagination cursor.
        - `size` (`Optional[int]`): Max rows (default 20).

        **Returns**
        - `Dict[str, Any]`: `{"drug": {"literatureOcurrences": {"count": int, "rows": [...]}}}`.
        """
        graphql_query = """
        query DrugLiteratureOcurrences(
            $chemblId: String!,
            $additionalIds: [String!],
            $startYear: Int,
            $startMonth: Int,
            $endYear: Int,
            $endMonth: Int,
            $cursor: String
        ) {
            drug(chemblId: $chemblId) {
                id
                name
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
            "chemblId": chembl_id,
            "additionalIds": additional_entity_ids,
            "startYear": start_year,
            "startMonth": start_month,
            "endYear": end_year,
            "endMonth": end_month,
            "cursor": cursor,
        }
        variables = {k: v for k, v in variables.items() if v is not None}

        result = await client._query(graphql_query, variables)

        if size is not None and isinstance(size, int) and size >= 0 and result.get("drug"):
            literature = result["drug"].get("literatureOcurrences")
            if literature and isinstance(literature, dict):
                rows = literature.get("rows")
                if isinstance(rows, list):
                    literature["rows"] = rows[:size]

        return result

    async def get_drug_similar_entities(
        self,
        client: OpenTargetsClient,
        chembl_id: str,
        threshold: Optional[float] = 0.5,
        size: int = 10,
        entity_names: Optional[List[str]] = None,
        additional_entity_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Find semantically similar drugs based on PubMed embeddings.

        **When to use**
        - Find drugs with similar literature profiles
        - Discover alternative compounds for research
        - Expand drug scope for comparative analysis

        **When not to use**
        - Finding drugs with same target (use `get_drug_linked_targets`)
        - Finding drugs for same indication (use indication data)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `chembl_id` (`str`): Drug identifier.
        - `threshold` (`Optional[float]`): Minimum similarity (0-1), default 0.5.
        - `size` (`int`): Max similar drugs (default 10).
        - `entity_names` (`Optional[List[str]]`): Entity types to include; defaults to `["drug"]`.
        - `additional_entity_ids` (`Optional[List[str]]`): Additional entity IDs for similarity context.

        **Returns**
        - `Dict[str, Any]`: `{"drug": {"similarEntities": [{"score": float, "object": {...}}, ...]}}`.
        """
        graphql_query = """
        query DrugSimilarEntities(
            $chemblId: String!,
            $threshold: Float,
            $size: Int!,
            $entityNames: [String!],
            $additionalIds: [String!]
        ) {
            drug(chemblId: $chemblId) {
                id
                name
                similarEntities(
                    threshold: $threshold,
                    size: $size,
                    entityNames: $entityNames,
                    additionalIds: $additionalIds
                ) {
                    score
                    object {
                        __typename
                        ... on Drug {
                            id
                            name
                            drugType
                            isApproved
                            maximumClinicalTrialPhase
                        }
                    }
                }
            }
        }
        """
        variables = {
            "chemblId": chembl_id,
            "threshold": threshold,
            "size": size,
            "entityNames": entity_names or ["drug"],
            "additionalIds": additional_entity_ids,
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

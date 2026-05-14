# src/opentargets_mcp/tools/drug/associations.py
"""
Defines API methods and MCP tools related to a drug's associations with other entities.
"""
from typing import Any, Dict, List, Optional
from ...queries import OpenTargetsClient
from ...utils import (
    add_legacy_drug_fields,
    build_literature_variables,
    filter_none_values,
    flatten_mechanism_targets,
    select_fields,
    trim_literature_occurrences,
    validate_required_int,
)

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
                indications {
                    count
                    rows {
                        id
                        maxClinicalStage
                        disease {
                            id
                            name
                            description
                            therapeuticAreas {
                                id
                                name
                            }
                        }
                        clinicalReports {
                            id
                            source
                            clinicalStage
                            trialPhase
                            trialOverallStatus
                            url
                        }
                    }
                }
            }
        }
        """
        result = await client._query(graphql_query, {"chemblId": chembl_id})
        drug = result.get("drug")
        if isinstance(drug, dict):
            indications = drug.pop("indications", None)
            if isinstance(indications, dict):
                rows = []
                for row in indications.get("rows", []) or []:
                    if not isinstance(row, dict):
                        continue
                    disease = row.get("disease")
                    if isinstance(disease, dict):
                        disease.setdefault("maxClinicalStage", row.get("maxClinicalStage"))
                        disease.setdefault("clinicalReports", row.get("clinicalReports"))
                        rows.append(disease)
                drug["linkedDiseases"] = {"count": len(rows), "rows": rows}
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
                mechanismsOfAction {
                    rows {
                        mechanismOfAction
                        actionType
                        targets {
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
        }
        """
        result = await client._query(graphql_query, {"chemblId": chembl_id})
        drug = result.get("drug")
        if isinstance(drug, dict):
            targets = flatten_mechanism_targets(
                drug.get("mechanismsOfAction", {}).get("rows", []),
                copy_mechanism_fields=True,
            )
            drug["linkedTargets"] = {
                "count": len(targets),
                "rows": targets,
            }
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
        result = await client._query(
            graphql_query,
            build_literature_variables(
                "chemblId",
                chembl_id,
                additional_entity_ids=additional_entity_ids,
                start_year=start_year,
                start_month=start_month,
                end_year=end_year,
                end_month=end_month,
                cursor=cursor,
            ),
        )
        return trim_literature_occurrences(result, "drug", size)

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
                            maximumClinicalStage
                        }
                    }
                }
            }
        }
        """
        validated_size = validate_required_int(size, "size")
        variables = {
            "chemblId": chembl_id,
            "threshold": threshold,
            "size": validated_size,
            "entityNames": entity_names or ["drug"],
            "additionalIds": additional_entity_ids,
        }
        result = await client._query(graphql_query, filter_none_values(variables))
        rows = result.get("drug", {}).get("similarEntities")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    add_legacy_drug_fields(row.get("object"))
        return result

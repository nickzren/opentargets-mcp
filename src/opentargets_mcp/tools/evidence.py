# src/opentargets_mcp/tools/evidence.py
"""
Defines API methods and MCP tools related to 'Evidence' linking targets and diseases.
"""
from typing import Any, Dict, List, Optional
from ..queries import OpenTargetsClient # Relative import

class EvidenceApi:
    """
    Contains methods to query evidence-specific data from the Open Targets GraphQL API.
    """

    async def get_target_disease_evidence(
        self,
        client: OpenTargetsClient,
        ensembl_id: str,
        efo_id: str,
        datasource_ids: Optional[List[str]] = None,
        size: int = 10,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve evidence strings linking a target to a disease.

        **When to use**
        - Audit the individual evidence components supporting a target–disease association
        - Filter results by datasource to focus on genetic, literature, or clinical sources
        - Implement paginated evidence views within conversational agents

        **When not to use**
        - Summarising association scores only (see target/disease association tools)
        - Exploring biomarkers specifically (use `get_target_disease_biomarkers`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client instance.
        - `ensembl_id` (`str`): Target identifier (`"ENSG..."`).
        - `efo_id` (`str`): Disease identifier (`"EFO..."`/`"MONDO..."`).
        - `datasource_ids` (`Optional[List[str]]`): Restrict to specific datasource IDs (e.g., `["eva", "ot_crispr"]`).
        - `size` (`int`): Maximum evidence rows to return per page (default 10).
        - `cursor` (`Optional[str]`): Cursor token from a previous call for pagination.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"evidences": {"count": int, "cursor": str, "rows": [{"id": str, "score": float, "datasourceId": str, "datatypeId": str, ...}], ...}}}`.

        **Errors**
        - Propagates GraphQL and network exceptions from `OpenTargetsClient`.

        **Example**
        ```python
        evidence_api = EvidenceApi()
        evidences = await evidence_api.get_target_disease_evidence(
            client, "ENSG00000157764", "EFO_0003884", datasource_ids=["eva"], size=5
        )
        print(len(evidences["target"]["evidences"]["rows"]))
        ```
        """
        # Note: The API structures evidence under the 'target' or 'disease' object.
        # This function queries via the 'target' object.
        graphql_query = """
        query TargetDiseaseEvidences(
            $ensemblId: String!,
            $efoId: String!, # API uses efoIds: [String!]
            $datasourceIds: [String!],
            $size: Int!,
            $cursor: String
        ) {
            target(ensemblId: $ensemblId) {
                evidences(
                    efoIds: [$efoId], # Pass efo_id as a list
                    datasourceIds: $datasourceIds,
                    size: $size,
                    cursor: $cursor
                ) {
                    count
                    cursor # For pagination
                    rows {
                        id # Evidence ID
                        score # Evidence score
                        datasourceId
                        datatypeId
                        diseaseFromSource
                        targetFromSourceId
                        disease { id, name } # Disease context for this evidence
                        target { id, approvedSymbol } # Target context
                        # Common evidence fields
                        literature # List of PMIDs
                        # Depending on datatypeId, specific fields will be populated, e.g.:
                        # ... on GeneticEvidence { variantId, variantRsId, gwasSampleCount, confidence }
                        # ... on SomaticMutation { functionalConsequenceId, numberOfSamplesWithMutationType, numberOfSamplesTested }
                        # ... on DrugsEvidence { clinicalPhase, clinicalStatus, mechanismOfAction, urls { name, url } }
                        # It's hard to list all specific fields due to polymorphism.
                        # The API will return relevant fields based on the evidence type.
                        # We can add specific fragments later if needed for common types.
                    }
                }
            }
        }
        """
        variables = {
            "ensemblId": ensembl_id,
            "efoId": efo_id,
            "datasourceIds": datasource_ids,
            "size": size,
            "cursor": cursor
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

    async def get_target_disease_biomarkers(
        self,
        client: OpenTargetsClient,
        ensembl_id: str,
        efo_id: str,
        size: int = 10, # Number of evidence strings to check for biomarkers
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Inspect evidence for biomarker annotations linking a target and disease.

        **When to use**
        - Highlight biomarker candidates referenced within clinical or literature evidence
        - Provide conversational answers about biomarkers associated with a therapeutic hypothesis
        - Explore biomarker metadata before diving into datasource-specific payloads

        **When not to use**
        - General evidence retrieval without biomarker focus (use `get_target_disease_evidence`)
        - Requesting structured biomarker ontologies (not all evidence types expose dedicated fields)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target Ensembl ID.
        - `efo_id` (`str`): Disease identifier.
        - `size` (`int`): Maximum evidence strings per page (default 10).
        - `cursor` (`Optional[str]`): Pagination cursor from a previous response.

        **Returns**
        - `Dict[str, Any]`: Response `{"target": {"evidences": {"rows": [{"id": str, "datasourceId": str, "biomarkerName": str, ...}], "count": int, "cursor": str}}}`. Presence of biomarker fields depends on datasource.

        **Errors**
        - GraphQL and transport errors propagate from `OpenTargetsClient`.

        **Example**
        ```python
        evidence_api = EvidenceApi()
        biomarker_rows = await evidence_api.get_target_disease_biomarkers(
            client, "ENSG00000157764", "EFO_0003884", size=5
        )
        print(biomarker_rows["target"]["evidences"]["rows"][0].get("biomarkerName"))
        ```
        """
        # Biomarkers are often part of the evidence strings.
        # The query provided by Claude looks for 'biomarkerName' and 'biomarkers' within evidence.
        graphql_query = """
        query TargetDiseaseBiomarkers(
            $ensemblId: String!,
            $efoId: String!,
            $size: Int!,
            $cursor: String
        ) {
            target(ensemblId: $ensemblId) {
                evidences(efoIds: [$efoId], size: $size, cursor: $cursor) {
                    count
                    cursor
                    rows {
                        id # Evidence ID
                        score
                        datasourceId
                        datatypeId
                        # Fields relevant to biomarkers as suggested by Claude's query
                        biomarkerName # If available directly
                        # The 'biomarkers' object in Claude's query might be specific to certain datasources
                        # or a simplified representation. The actual API might structure this differently.
                        # Let's try to query for fields that are likely to contain biomarker info.
                        # This might be within specific evidence types (e.g., clinical trials).
                        # For now, we'll fetch general evidence and the client might need to parse.
                        # If a specific 'biomarkers' field exists on evidence rows, it would be here.
                        # The platform schema doesn't show a generic 'biomarkers' field on the EvidenceRow.
                        # It's usually within specific evidence types like DrugEvidence -> biomarker.
                        # Example for DrugEvidence (if this evidence row is of that type):
                        # ... on DrugEvidence {
                        #   biomarker {
                        #     name
                        #     geneExpression { name, id { id, name } }
                        #     geneticVariation { id, name, functionalConsequenceId { id, label } }
                        #   }
                        # }
                        # To get this, we'd need to use GraphQL fragments for different evidence types.
                        # For simplicity now, we'll return the evidence rows and users can inspect.
                        # A more advanced version could use fragments.
                        disease { id, name }
                        target { id, approvedSymbol }
                    }
                }
            }
        }
        """
        # This tool will return evidence strings. The presence and structure of biomarker
        # data within these strings can vary. Users may need to inspect the results,
        # particularly if the evidence comes from clinical trials or specific biomarker studies.
        variables = {
            "ensemblId": ensembl_id,
            "efoId": efo_id,
            "size": size,
            "cursor": cursor
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

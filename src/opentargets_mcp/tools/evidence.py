# src/opentargets_mcp/tools/evidence.py
"""
Defines API methods and MCP tools related to 'Evidence' linking targets and diseases.
"""
from typing import Any, Dict, List, Optional
import mcp.types as types
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
        """Get evidence linking a specific target to a specific disease."""
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
        """Get biomarker information from evidence linking a target to a disease."""
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


EVIDENCE_TOOLS = [
    types.Tool(
        name="get_target_disease_evidence",
        description="Get evidence linking a specific target to a specific disease. Supports pagination.",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {"type": "string", "description": "Ensembl ID of the target."},
                "efo_id": {"type": "string", "description": "EFO ID of the disease."},
                "datasource_ids": {"type": "array", "items": {"type": "string"}, "description": "Filter by specific datasource IDs (e.g., 'eva', 'uniprot'). Optional."},
                "size": {"type": "number", "description": "Number of evidence items per page (default: 10).", "default": 10},
                "cursor": {"type": "string", "description": "Cursor for pagination from a previous response. Optional."}
            },
            "required": ["ensembl_id", "efo_id"]
        }
    ),
    types.Tool(
        name="get_target_disease_biomarkers",
        description="Get biomarker information from evidence linking a target to a disease. This tool returns evidence strings which may contain biomarker details.",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {"type": "string", "description": "Ensembl ID of the target."},
                "efo_id": {"type": "string", "description": "EFO ID of the disease."},
                "size": {"type": "number", "description": "Number of evidence items to scan for biomarkers (default: 10).", "default": 10},
                "cursor": {"type": "string", "description": "Cursor for pagination from a previous response. Optional."}
            },
            "required": ["ensembl_id", "efo_id"]
        }
    )
]

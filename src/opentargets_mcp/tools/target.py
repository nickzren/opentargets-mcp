# src/opentargets_mcp/tools/target.py
"""
Defines API methods and MCP tools related to 'Target' entities in Open Targets.
"""
from typing import Any, Dict, List, Optional
import mcp.types as types
from ..queries import OpenTargetsClient # Relative import

class TargetApi:
    """
    Contains methods to query target-specific data from the Open Targets GraphQL API.
    Each method corresponds to a potential tool that can be called by an MCP client.
    """

    async def get_target_info(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific target by its Ensembl ID."""
        graphql_query = """
        query TargetInfo($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                approvedName
                biotype
                functionDescriptions
                synonyms { label, source }
                genomicLocation { chromosome, start, end, strand }
                proteinIds { id, source }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

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
        """Get drugs/compounds known to interact with a specific target.
        Note: page_index and page_size are not used in this query as the API indicated 'page' is an unknown argument for knownDrugs.
        This will fetch all known drugs for the target.
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

    async def get_target_expression(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get RNA and protein expression data for a target across tissues."""
        graphql_query = """
        query TargetExpression($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                expressions {
                    tissue { id, label, organs, anatomicalSystems }
                    rna { level, unit, value, zscore }
                    protein { level, reliability, cellType { name, level, reliability } }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_genetic_constraint(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get genetic constraint scores (e.g., gnomAD pLI, LOEUF) for a target."""
        graphql_query = """
        query TargetConstraint($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                geneticConstraint {
                    constraintType
                    score
                    exp
                    obs
                    oe
                    oeLower
                    oeUpper
                    upperBin
                    upperBin6
                    upperRank
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_mouse_phenotypes(self, client: OpenTargetsClient, ensembl_id: str, page_index: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """Get mouse knockout phenotypes associated with a target from MGI and IMPC.
        Note: page_index and page_size are not used as API indicated 'page' is an unknown argument.
        This will fetch all mouse phenotypes for the target.
        """
        graphql_query = """
        query TargetMousePhenotypes($ensemblId: String!) { 
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                mousePhenotypes { 
                    modelPhenotypeId
                    modelPhenotypeLabel
                    biologicalModels {
                        id
                        allelicComposition
                        geneticBackground
                    }
                    modelPhenotypeClasses {
                        id
                        label
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_pathways_and_go_terms(self, client: OpenTargetsClient, ensembl_id: str, page_index: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """Get pathway (e.g., Reactome) and Gene Ontology term annotations for a target.
        Note: page_index and page_size are not used as API indicated 'page' is an unknown argument.
        This will fetch all pathways and GO terms.
        """
        graphql_query = """
        query TargetPathwaysAndGOTerms($ensemblId: String!) { 
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                pathways { 
                    pathway
                    pathwayId
                    topLevelTerm
                }
                geneOntology { 
                    aspect
                    geneProduct
                    evidence
                    source
                    term {
                         id
                         name
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_interactions(self, client: OpenTargetsClient, ensembl_id: str, source_database: Optional[str] = None, score_threshold: Optional[float] = None, page_index: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """Get protein-protein interactions for a target from sources like IntAct, Reactome, Signor."""
        graphql_query = """
        query TargetInteractions(
            $ensemblId: String!, 
            $sourceDatabase: String,
            $scoreThreshold: Float,
            $pageIndex: Int!, 
            $pageSize: Int!
        ) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                interactions(
                    sourceDatabase: $sourceDatabase, 
                    scoreThreshold: $scoreThreshold, 
                    page: {index: $pageIndex, size: $pageSize}
                ) {
                    count
                    rows {
                        intA
                        intB
                        score
                        sourceDatabase
                        targetA { id, approvedSymbol }
                        targetB { id, approvedSymbol }
                        evidences {
                            interactionIdentifier
                            interactionDetectionMethodShortName
                            hostOrganismScientificName
                            participantDetectionMethodA { miIdentifier, shortName }
                            participantDetectionMethodB { miIdentifier, shortName }
                        }
                    }
                }
            }
        }
        """
        variables = {
            "ensemblId": ensembl_id,
            "sourceDatabase": source_database,
            "scoreThreshold": score_threshold,
            "pageIndex": page_index,
            "pageSize": page_size
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

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
        """Get literature co-occurrences for a target, optionally with other entities (diseases, drugs).
        Note: 'size' parameter is not used in GQL query as API reported it as unknown.
        """
        graphql_query = """
        query TargetLiteratureOcurrences( 
            $ensemblId: String!,
            $additionalIds: [String!],
            $startYear: Int,
            $endYear: Int,
            $cursor: String
            # $size: Int! removed from query variables
        ) {
            target(ensemblId: $ensemblId) {
                literatureOcurrences( # Corrected field name
                    additionalIds: $additionalIds,
                    startYear: $startYear,
                    endYear: $endYear,
                    cursor: $cursor
                    # size: $size argument removed
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
            # size is not passed to variables for this query
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

    async def get_target_prioritization(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Get target prioritization scores from various sources."""
        graphql_query = """
        query TargetPrioritisation($ensemblId: String!) { 
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                prioritisation { # This field returns KeyValueArray according to API error
                    items {      # KeyValueArray has an 'items' field
                        key
                        value
                        # label, description, link, source are not on KeyValue, but on TargetPrioritisationScore
                        # If API returns KeyValueArray, we can only get key/value here.
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})


TARGET_TOOLS = [
    types.Tool(
        name="get_target_info",
        description="Get detailed information about a specific target by its Ensembl ID (e.g., ENSG00000157764 for BRAF).",
        inputSchema={
            "type": "object",
            "properties": {"ensembl_id": {"type": "string", "description": "Ensembl ID of the target."}},
            "required": ["ensembl_id"]
        }
    ),
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
        name="get_target_expression",
        description="Get RNA and protein expression data for a target across tissues.",
        inputSchema={
            "type": "object",
            "properties": {"ensembl_id": {"type": "string", "description": "Ensembl ID of the target."}},
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_genetic_constraint",
        description="Get genetic constraint scores (e.g., gnomAD pLI, LOEUF) for a target.",
        inputSchema={
            "type": "object",
            "properties": {"ensembl_id": {"type": "string", "description": "Ensembl ID of the target."}},
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_mouse_phenotypes",
        description="Get mouse knockout phenotypes associated with a target.",
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
        name="get_target_pathways_and_go_terms",
        description="Get pathway (e.g., Reactome) and Gene Ontology term annotations for a target.",
         inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {"type": "string", "description": "Ensembl ID of the target."},
                "page_index": {"type": "number", "description": "Page number (default: 0). Not used by API for these endpoints.", "default": 0},
                "page_size": {"type": "number", "description": "Results per page (default: 10). Not used by API for these endpoints.", "default": 10}
            },
            "required": ["ensembl_id"]
        }
    ),
    types.Tool(
        name="get_target_interactions",
        description="Get protein-protein interactions for a target.",
        inputSchema={
            "type": "object",
            "properties": {
                "ensembl_id": {"type": "string", "description": "Ensembl ID of the target."},
                "source_database": {"type": "string", "description": "Filter by source database (e.g., 'intact', 'reactome', 'signor'). Optional."},
                "score_threshold": {"type": "number", "description": "Minimum interaction score threshold. Optional."},
                "page_index": {"type": "number", "description": "Page number for results (default: 0).", "default": 0},
                "page_size": {"type": "number", "description": "Number of results per page (default: 10).", "default": 10}
            },
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
    types.Tool(
        name="get_target_prioritization",
        description="Get target prioritization scores from various sources.",
        inputSchema={
            "type": "object",
            "properties": {"ensembl_id": {"type": "string", "description": "Ensembl ID of the target."}},
            "required": ["ensembl_id"]
        }
    )
]

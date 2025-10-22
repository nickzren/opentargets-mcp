# src/opentargets_mcp/tools/target/biology.py
"""
Defines API methods and MCP tools related to a target's biology.
"""
from typing import Any, Dict, Optional
from ...queries import OpenTargetsClient

class TargetBiologyApi:
    """
    Contains methods to query a target's biological attributes.
    """
    async def get_target_expression(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Return RNA and protein expression profiles for a target across tissues.

        **When to use**
        - Provide tissue-context for a target in exploratory analyses
        - Compare RNA versus protein expression across anatomical systems
        - Identify tissues with elevated expression before target safety review

        **When not to use**
        - Exploring gene constraint or essentiality (use dedicated tools)
        - Searching for targets by tissue (use search + filtering first)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "expressions": [{"tissue": {...}, "rna": {...}, "protein": {...}}, ...]}}`.

        **Errors**
        - GraphQL/network exceptions propagate via the client.

        **Example**
        ```python
        biology_api = TargetBiologyApi()
        expression = await biology_api.get_target_expression(client, "ENSG00000157764")
        print(expression["target"]["expressions"][0]["tissue"]["label"])
        ```
        """
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

    async def get_target_pathways_and_go_terms(
        self,
        client: OpenTargetsClient,
        ensembl_id: str,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """List pathway memberships and Gene Ontology annotations for a target.

        **When to use**
        - Summarise functional context (Reactome pathways, GO terms) for a gene
        - Support reasoning about biological processes in conversational flows
        - Provide curated annotations for enrichment analyses

        **When not to use**
        - Looking for protein–protein interactions (use `get_target_interactions`)
        - Retrieving expression or phenotype data (use respective tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.
        - `page_index` (`int`): Reserved for future pagination (currently unused).
        - `page_size` (`int`): Reserved parameter (API returns all entries).

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "pathways": [...], "geneOntology": [...]}}`.

        **Errors**
        - GraphQL/network errors bubble up from the client.

        **Example**
        ```python
        biology_api = TargetBiologyApi()
        annotations = await biology_api.get_target_pathways_and_go_terms(client, "ENSG00000157764")
        print(annotations["target"]["pathways"][0]["pathway"])
        ```
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

    async def get_target_homologues(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Retrieve cross-species homologues for a target gene.

        **When to use**
        - Investigate orthologous relationships for translational modelling
        - Determine conservation of a target across organisms
        - Surface identity percentages for similarity assessments

        **When not to use**
        - Evaluating phenotypes (use mouse phenotype tool)
        - Checking human-only annotations (use identity/biology tools instead)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "homologues": [{"speciesId": str, "targetGeneSymbol": str, "homologyType": str, ...}, ...]}}`.

        **Errors**
        - Propagates GraphQL/network exceptions.

        **Example**
        ```python
        biology_api = TargetBiologyApi()
        homologues = await biology_api.get_target_homologues(client, "ENSG00000157764")
        print(homologues["target"]["homologues"][0]["speciesName"])
        ```
        """
        graphql_query = """
        query TargetHomologues($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                homologues {
                    speciesId
                    speciesName
                    targetGeneId
                    targetGeneSymbol
                    homologyType
                    queryPercentageIdentity
                    targetPercentageIdentity
                    isHighConfidence
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_subcellular_locations(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Return subcellular localisation annotations for a target.

        **When to use**
        - Assess where within the cell a protein is localised for target validation
        - Provide localisation context (e.g., nucleus vs membrane) in dialogue
        - Support tractability discussions that depend on cellular compartment

        **When not to use**
        - Seeking interaction partners or pathways (use corresponding tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "subcellularLocations": [{"location": str, "source": str, "termSL": str, "labelSL": str}, ...]}}`.

        **Errors**
        - GraphQL/network exceptions propagate.

        **Example**
        ```python
        biology_api = TargetBiologyApi()
        locations = await biology_api.get_target_subcellular_locations(client, "ENSG00000157764")
        print(locations["target"]["subcellularLocations"][0]["location"])
        ```
        """
        graphql_query = """
        query TargetSubcellularLocations($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                subcellularLocations {
                    location
                    source
                    termSL
                    labelSL
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_genetic_constraint(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Fetch genetic constraint metrics (gnomAD) for a target.

        **When to use**
        - Understand intolerance to variation (LOEUF, pLI) during target selection
        - Provide constraint values for safety or essentiality assessments
        - Compare expected vs observed variant counts

        **When not to use**
        - Looking for cellular essentiality (use DepMap tool)
        - Exploring disease associations (use association modules)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "geneticConstraint": [{"constraintType": str, "score": float, "exp": float, "obs": float, ...}, ...]}}`.

        **Errors**
        - GraphQL/network errors bubble up.

        **Example**
        ```python
        biology_api = TargetBiologyApi()
        constraint = await biology_api.get_target_genetic_constraint(client, "ENSG00000157764")
        print(constraint["target"]["geneticConstraint"][0]["constraintType"])
        ```
        """
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

    async def get_target_mouse_phenotypes(
        self,
        client: OpenTargetsClient,
        ensembl_id: str,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Retrieve mouse knockout phenotypes associated with a target.

        **When to use**
        - Understand in vivo phenotypes observed in MGI/IMPC models
        - Provide supporting evidence for target function through animal models
        - Inform safety assessments by reviewing phenotype classes

        **When not to use**
        - Fetching human evidence or associations (use relevant tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.
        - `page_index` (`int`): Reserved pagination parameter (currently unused).
        - `page_size` (`int`): Reserved parameter; data returned is not paginated by API.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "mousePhenotypes": [{"modelPhenotypeId": str, "modelPhenotypeLabel": str, "biologicalModels": [...], "modelPhenotypeClasses": [...]}, ...]}}`.

        **Errors**
        - Propagates GraphQL/network exceptions.

        **Example**
        ```python
        biology_api = TargetBiologyApi()
        phenotypes = await biology_api.get_target_mouse_phenotypes(client, "ENSG00000157764")
        print(phenotypes["target"]["mousePhenotypes"][0]["modelPhenotypeLabel"])
        ```
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

    async def get_target_hallmarks(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Return cancer hallmark annotations associated with a target.

        **When to use**
        - Describe how a target contributes to cancer hallmark capabilities
        - Provide curated references (PMIDs) relating a gene to hallmark attributes
        - Support oncology-focused prioritisation workflows

        **When not to use**
        - Examining non-oncology evidence (consider other modules)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "hallmarks": {"attributes": [...], "cancerHallmarks": [...]}}}`.

        **Errors**
        - GraphQL/network errors propagate.

        **Example**
        ```python
        biology_api = TargetBiologyApi()
        hallmarks = await biology_api.get_target_hallmarks(client, "ENSG00000157764")
        print(hallmarks["target"]["hallmarks"]["cancerHallmarks"][0]["label"])
        ```
        """
        graphql_query = """
        query TargetHallmarks($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                hallmarks {
                    attributes {
                        name
                        description
                        pmid
                    }
                    cancerHallmarks {
                        label
                        impact
                        description
                        pmid
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_depmap_essentiality(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Fetch DepMap CRISPR essentiality scores across cell lines.

        **When to use**
        - Evaluate whether a target is essential across cancer cell lines
        - Provide gene effect scores with lineage context in dialogue
        - Combine essentiality findings with other viability metrics

        **When not to use**
        - Looking for genetic constraint metrics (use `get_target_genetic_constraint`)
        - Exploring interaction partners (use `get_target_interactions`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "isEssential": bool, "depMapEssentiality": [{"tissueId": str, "screens": [{"depmapId": str, "cellLineName": str, "geneEffect": float, ...}, ...]}, ...]}}`.

        **Errors**
        - GraphQL/network exceptions propagate.

        **Example**
        ```python
        biology_api = TargetBiologyApi()
        depmap = await biology_api.get_target_depmap_essentiality(client, "ENSG00000157764")
        print(depmap["target"]["depMapEssentiality"][0]["tissueName"])
        ```
        """
        graphql_query = """
        query TargetDepMapEssentiality($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                isEssential
                depMapEssentiality {
                    tissueId
                    tissueName
                    screens {
                        depmapId
                        cellLineName
                        diseaseCellLineId
                        diseaseFromSource
                        geneEffect
                        expression
                        mutation
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_interactions(
        self,
        client: OpenTargetsClient,
        ensembl_id: str,
        source_database: Optional[str] = None,
        score_threshold: Optional[float] = None,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Retrieve protein interaction partners for a target from curated databases.

        **When to use**
        - Display interaction partners with confidence scores and datasource provenance
        - Filter interactions by database (IntAct, Reactome, SIGNOR, etc.)
        - Build network visualisations or answer connectivity questions

        **When not to use**
        - Exploring genetic associations or pathways (use other tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.
        - `source_database` (`Optional[str]`): Limit to a specific interaction datasource.
        - `score_threshold` (`Optional[float]`): Minimum confidence score (0–1).
        - `page_index` (`int`): Page index for pagination.
        - `page_size` (`int`): Number of interaction rows per page (default 10).

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "interactions": {"count": int, "rows": [{"intA": str, "targetB": {...}, "score": float, "sourceDatabase": str, ...}], "pageInfo": {...}}}}`.

        **Errors**
        - GraphQL/network exceptions are propagated by the client.

        **Example**
        ```python
        biology_api = TargetBiologyApi()
        interactions = await biology_api.get_target_interactions(
            client, "ENSG00000157764", source_database="intact", score_threshold=0.5
        )
        print(interactions["target"]["interactions"]["rows"][0]["score"])
        ```
        """
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

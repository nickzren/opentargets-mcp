# src/opentargets_mcp/tools/target/biology.py
"""
Defines API methods and MCP tools related to a target's biology.
"""
from typing import Any, Dict, List, Optional
from ...queries import OpenTargetsClient

class TargetBiologyApi:
    """
    Contains methods to query a target's biological attributes.
    """
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

    async def get_target_pathways_and_go_terms(self, client: OpenTargetsClient, ensembl_id: str, page_index: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """Get pathway (e.g., Reactome) and Gene Ontology term annotations for a target."""
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
        """Get homologues for a target across species."""
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
        """Get subcellular location information for a target."""
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
        """Get mouse knockout phenotypes associated with a target from MGI and IMPC."""
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
        """Get cancer hallmarks associated with a target."""
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
        """Get DepMap essentiality data for a target across cell lines."""
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


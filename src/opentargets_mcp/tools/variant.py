# src/opentargets_mcp/tools/variant.py
"""
Defines API methods and MCP tools related to 'Variant' entities in Open Targets.
"""
from typing import Any, Dict, List, Optional
import mcp.types as types
from ..queries import OpenTargetsClient

class VariantApi:
    """
    Contains methods to query variant-specific data from the Open Targets GraphQL API.
    """

    async def get_variant_info(self, client: OpenTargetsClient, variant_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific variant by its ID."""
        graphql_query = """
        query VariantInfo($variantId: String!) {
            variant(variantId: $variantId) {
                id
                variantDescription
                chromosome
                position
                referenceAllele
                alternateAllele
                hgvsId
                rsIds
                dbXrefs {
                    id
                    source
                }
                alleleFrequencies {
                    populationName
                    alleleFrequency
                }
                mostSevereConsequence {
                    id
                    label
                }
                transcriptConsequences {
                    transcriptId
                    aminoAcidChange
                    codons
                    consequenceScore
                    impact
                    lofteePrediction
                    polyphenPrediction
                    siftPrediction
                    isEnsemblCanonical
                    distanceFromTss
                    uniprotAccessions
                    target {
                        id
                        approvedSymbol
                    }
                    variantConsequences {
                        id
                        label
                    }
                }
                variantEffect {
                    score
                    normalisedScore
                    method
                    assessment
                    assessmentFlag
                    target {
                        id
                        approvedSymbol
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"variantId": variant_id})

    async def get_variant_credible_sets(
        self, 
        client: OpenTargetsClient, 
        variant_id: str, 
        study_types: Optional[List[str]] = None,
        page_index: int = 0, 
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Get credible sets associated with a variant."""
        graphql_query = """
        query VariantCredibleSets(
            $variantId: String!,
            $studyTypes: [StudyTypeEnum!],
            $pageIndex: Int!,
            $pageSize: Int!
        ) {
            variant(variantId: $variantId) {
                id
                rsIds
                credibleSets(
                    studyTypes: $studyTypes,
                    page: {index: $pageIndex, size: $pageSize}
                ) {
                    count
                    rows {
                        studyLocusId
                        studyId
                        studyType
                        chromosome
                        position
                        region
                        beta
                        zScore
                        pValueMantissa
                        pValueExponent
                        standardError
                        confidence
                        finemappingMethod
                        credibleSetIndex
                        credibleSetlog10BF
                        purityMeanR2
                        purityMinR2
                        study {
                            id
                            traitFromSource
                            projectId
                            pubmedId
                            publicationFirstAuthor
                            publicationDate
                        }
                        variant {
                            id
                            rsIds
                        }
                    }
                }
            }
        }
        """
        variables = {
            "variantId": variant_id,
            "studyTypes": study_types,
            "pageIndex": page_index,
            "pageSize": page_size
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

    async def get_variant_pharmacogenomics(
        self, 
        client: OpenTargetsClient, 
        variant_id: str, 
        page_index: int = 0, 
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Get pharmacogenomics data for a variant."""
        graphql_query = """
        query VariantPharmacogenomics($variantId: String!, $pageIndex: Int!, $pageSize: Int!) {
            variant(variantId: $variantId) {
                id
                rsIds
                pharmacogenomics(page: {index: $pageIndex, size: $pageSize}) {
                    variantId
                    variantRsId
                    variantFunctionalConsequenceId
                    targetFromSourceId
                    genotypeId
                    genotype
                    genotypeAnnotationText
                    phenotypeText
                    phenotypeFromSourceId
                    pgxCategory
                    evidenceLevel
                    datasourceId
                    datatypeId
                    studyId
                    literature
                    haplotypeId
                    haplotypeFromSourceId
                    isDirectTarget
                    variantFunctionalConsequence {
                        id
                        label
                    }
                    target {
                        id
                        approvedSymbol
                        approvedName
                    }
                    drugs {
                        drugId
                        drugFromSource
                        drug {
                            id
                            name
                            drugType
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"variantId": variant_id, "pageIndex": page_index, "pageSize": page_size})

    async def get_variant_evidences(
        self,
        client: OpenTargetsClient,
        variant_id: str,
        datasource_ids: Optional[List[str]] = None,
        size: int = 10,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get evidence associated with a variant."""
        graphql_query = """
        query VariantEvidences(
            $variantId: String!,
            $datasourceIds: [String!],
            $size: Int!,
            $cursor: String
        ) {
            variant(variantId: $variantId) {
                id
                rsIds
                evidences(
                    datasourceIds: $datasourceIds,
                    size: $size,
                    cursor: $cursor
                ) {
                    count
                    cursor
                    rows {
                        id
                        score
                        datasourceId
                        datatypeId
                        # variantId  <- THIS LINE WAS REMOVED
                        variantRsId
                        variantEffect
                        confidence
                        literature
                        studyId
                        beta
                        pValueMantissa
                        pValueExponent
                        oddsRatio
                        oddsRatioConfidenceIntervalLower
                        oddsRatioConfidenceIntervalUpper
                        target {
                            id
                            approvedSymbol
                        }
                        disease {
                            id
                            name
                        }
                        variantFunctionalConsequence {
                            id
                            label
                        }
                    }
                }
            }
        }
        """
        variables = {
            "variantId": variant_id,
            "datasourceIds": datasource_ids,
            "size": size,
            "cursor": cursor
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)


VARIANT_TOOLS = [
    types.Tool(
        name="get_variant_info",
        description="Get detailed information about a specific variant by its ID (e.g., '1_154453788_C_T' or rs12345).",
        inputSchema={
            "type": "object",
            "properties": {"variant_id": {"type": "string", "description": "Variant ID (CHROM_POS_REF_ALT format or rsID)."}},
            "required": ["variant_id"]
        }
    ),
    types.Tool(
        name="get_variant_credible_sets",
        description="Get credible sets (fine-mapping results) associated with a variant from GWAS studies.",
        inputSchema={
            "type": "object",
            "properties": {
                "variant_id": {"type": "string", "description": "Variant ID (CHROM_POS_REF_ALT format or rsID)."},
                "study_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by study types (e.g., ['gwas', 'eqtl', 'pqtl']). Optional."
                },
                "page_index": {"type": "number", "description": "Page number for results (default: 0).", "default": 0},
                "page_size": {"type": "number", "description": "Number of results per page (default: 10).", "default": 10}
            },
            "required": ["variant_id"]
        }
    ),
    types.Tool(
        name="get_variant_pharmacogenomics",
        description="Get pharmacogenomics data showing how genetic variants affect drug response.",
        inputSchema={
            "type": "object",
            "properties": {
                "variant_id": {"type": "string", "description": "Variant ID (CHROM_POS_REF_ALT format or rsID)."},
                "page_index": {"type": "number", "description": "Page number for results (default: 0).", "default": 0},
                "page_size": {"type": "number", "description": "Number of results per page (default: 10).", "default": 10}
            },
            "required": ["variant_id"]
        }
    ),
    types.Tool(
        name="get_variant_evidences",
        description="Get all evidence (GWAS, functional, etc.) associated with a variant.",
        inputSchema={
            "type": "object",
            "properties": {
                "variant_id": {"type": "string", "description": "Variant ID (CHROM_POS_REF_ALT format or rsID)."},
                "datasource_ids": {"type": "array", "items": {"type": "string"}, "description": "Filter by specific datasource IDs. Optional."},
                "size": {"type": "number", "description": "Number of evidence items per page (default: 10).", "default": 10},
                "cursor": {"type": "string", "description": "Cursor for pagination from a previous response. Optional."}
            },
            "required": ["variant_id"]
        }
    )
]
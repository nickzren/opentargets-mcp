# src/opentargets_mcp/tools/study.py
"""
Defines API methods and MCP tools related to 'Study' entities in Open Targets.
"""
from typing import Any, Dict, List, Optional
from ..queries import OpenTargetsClient

class StudyApi:
    """
    Contains methods to query study-specific data from the Open Targets GraphQL API.
    """

    async def get_study_info(self, client: OpenTargetsClient, study_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific GWAS study."""
        graphql_query = """
        query StudyInfo($studyId: String!) {
            study(studyId: $studyId) {
                id
                studyType
                projectId
                traitFromSource
                condition
                pubmedId
                publicationTitle
                publicationJournal
                publicationFirstAuthor
                publicationDate
                cohorts
                hasSumstats
                summarystatsLocation
                initialSampleSize
                nSamples
                nCases
                nControls
                analysisFlags
                qualityControls
                ldPopulationStructure {
                    ldPopulation
                    relativeSampleSize
                }
                discoverySamples {
                    ancestry
                    sampleSize
                }
                replicationSamples {
                    ancestry
                    sampleSize
                }
                sumstatQCValues {
                    QCCheckName
                    QCCheckValue
                }
                target {
                    id
                    approvedSymbol
                }
                biosample {
                    biosampleId
                    biosampleName
                    description
                }
                diseases {
                    id
                    name
                    therapeuticAreas {
                        id
                        name
                    }
                }
                backgroundTraits {
                    id
                    name
                }
            }
        }
        """
        return await client._query(graphql_query, {"studyId": study_id})

    async def get_studies_by_disease(
        self,
        client: OpenTargetsClient,
        disease_ids: List[str],
        enable_indirect: bool = False,
        study_id: Optional[str] = None,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Get studies associated with diseases."""
        graphql_query = """
        query StudiesByDisease(
            $diseaseIds: [String!],
            $enableIndirect: Boolean,
            $studyId: String,
            $pageIndex: Int!,
            $pageSize: Int!
        ) {
            studies(
                diseaseIds: $diseaseIds,
                enableIndirect: $enableIndirect,
                studyId: $studyId,
                page: {index: $pageIndex, size: $pageSize}
            ) {
                count
                rows {
                    id
                    studyType
                    traitFromSource
                    pubmedId
                    publicationFirstAuthor
                    publicationDate
                    nSamples
                    nCases
                    nControls
                    cohorts
                    analysisFlags
                    diseases {
                        id
                        name
                    }
                    target {
                        id
                        approvedSymbol
                    }
                }
            }
        }
        """
        variables = {
            "diseaseIds": disease_ids,
            "enableIndirect": enable_indirect,
            "studyId": study_id,
            "pageIndex": page_index,
            "pageSize": page_size
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

    async def get_study_credible_sets(
        self,
        client: OpenTargetsClient,
        study_id: str,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Get credible sets for a study."""
        graphql_query = """
        query StudyCredibleSets($studyId: String!, $pageIndex: Int!, $pageSize: Int!) {
            study(studyId: $studyId) {
                id
                studyType
                traitFromSource
                credibleSets(page: {index: $pageIndex, size: $pageSize}) {
                    count
                    rows {
                        studyLocusId
                        studyId
                        chromosome
                        position
                        region
                        locusStart
                        locusEnd
                        credibleSetIndex
                        credibleSetlog10BF
                        finemappingMethod
                        purityMeanR2
                        purityMinR2
                        zScore
                        beta
                        standardError
                        pValueMantissa
                        pValueExponent
                        effectAlleleFrequencyFromSource
                        confidence # <- This line is corrected
                        variant {
                            id
                            rsIds
                            referenceAllele
                            alternateAllele
                        }
                        locus(page: {index: 0, size: 5}) {
                            count
                            rows {
                                is95CredibleSet
                                is99CredibleSet
                                posteriorProbability
                                logBF
                                pValueMantissa
                                pValueExponent
                                beta
                                standardError
                                r2Overall
                                variant {
                                    id
                                    rsIds
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"studyId": study_id, "pageIndex": page_index, "pageSize": page_size})

    async def get_credible_set_by_id(self, client: OpenTargetsClient, study_locus_id: str) -> Dict[str, Any]:
        """Get a specific credible set by its study-locus ID."""
        graphql_query = """
        query CredibleSetById($studyLocusId: String!) {
            credibleSet(studyLocusId: $studyLocusId) {
                studyLocusId
                studyId
                studyType
                chromosome
                position
                region
                locusStart
                locusEnd
                credibleSetIndex
                credibleSetlog10BF
                finemappingMethod
                confidence
                purityMeanR2
                purityMinR2
                zScore
                beta
                standardError
                pValueMantissa
                pValueExponent
                effectAlleleFrequencyFromSource
                qtlGeneId
                isTransQtl
                study {
                    id
                    traitFromSource
                    pubmedId
                    publicationFirstAuthor
                }
                variant {
                    id
                    rsIds
                    referenceAllele
                    alternateAllele
                    mostSevereConsequence {
                        id
                        label
                    }
                }
                l2GPredictions(page: {index: 0, size: 10}) {
                    count
                    rows {
                        studyLocusId
                        score
                        shapBaseValue
                        target {
                            id
                            approvedSymbol
                        }
                        features {
                            name
                            value
                            shapValue
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"studyLocusId": study_locus_id})


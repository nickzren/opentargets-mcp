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
        """Retrieve metadata and cohort details for a GWAS study.

        **When to use**
        - Confirm study attributes (trait, cohorts, publication) before analysing loci
        - Provide study summaries in conversational responses
        - Access LD population structure and QC fields for deeper analysis

        **When not to use**
        - Listing studies for a disease (use `get_studies_by_disease`)
        - Obtaining credible sets or loci (use `get_study_credible_sets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `study_id` (`str`): Study identifier such as `"GCST90002357"`.

        **Returns**
        - `Dict[str, Any]`: `{"study": {"id": str, "studyType": str, "traitFromSource": str, "publicationTitle": str, "nSamples": int, ...}}`.

        **Errors**
        - GraphQL/network exceptions propagate via the client.

        **Example**
        ```python
        study_api = StudyApi()
        study = await study_api.get_study_info(client, "GCST90002357")
        print(study["study"]["traitFromSource"])
        ```
        """
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
        """List studies linked to one or more diseases.

        **When to use**
        - Find GWAS or other studies relevant to a disease programme
        - Filter by code-reported indirect associations (via `enable_indirect`)
        - Combine pagination with user prompts to explore multiple pages

        **When not to use**
        - Fetching detailed study metadata (use `get_study_info`)
        - Investigating credible sets or loci (use `get_study_credible_sets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `disease_ids` (`List[str]`): One or more EFO/MONDO IDs.
        - `enable_indirect` (`bool`): Include indirectly associated studies (default `False`).
        - `study_id` (`Optional[str]`): Restrict to a specific study if provided.
        - `page_index` (`int`): Zero-based page index (default 0).
        - `page_size` (`int`): Number of study rows per page (default 10).

        **Returns**
        - `Dict[str, Any]`: `{"studies": {"count": int, "rows": [{"id": str, "traitFromSource": str, "nSamples": int, ...}, ...]}}`.

        **Errors**
        - GraphQL/network exceptions bubble up from the client.

        **Example**
        ```python
        study_api = StudyApi()
        studies = await study_api.get_studies_by_disease(client, ["EFO_0003884"], page_size=5)
        print([row["id"] for row in studies["studies"]["rows"]])
        ```
        """
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
        """Retrieve fine-mapped credible sets for a study.

        **When to use**
        - Examine loci from fine-mapping analyses with posterior probabilities
        - Provide result tables that include variant-level annotations
        - Fetch high-confidence intervals before prioritising causal variants

        **When not to use**
        - Accessing a single locus by ID (use `get_credible_set_by_id`)
        - Reviewing study metadata alone (use `get_study_info`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `study_id` (`str`): Study identifier.
        - `page_index` (`int`): Zero-based page (default 0).
        - `page_size` (`int`): Number of credible set rows per page (default 10).

        **Returns**
        - `Dict[str, Any]`: `{"study": {"id": str, "credibleSets": {"count": int, "rows": [{"studyLocusId": str, "credibleSetIndex": int, "variant": {...}, "locus": {...}}, ...]}}}`.

        **Errors**
        - GraphQL/network exceptions propagate via the client.

        **Example**
        ```python
        study_api = StudyApi()
        credible = await study_api.get_study_credible_sets(client, "GCST90002357", page_size=3)
        print(credible["study"]["credibleSets"]["rows"][0]["studyLocusId"])
        ```
        """
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
        """Fetch detailed information for a specific study locus credible set.

        **When to use**
        - Drill into a single credible set returned from pagination results
        - Examine locus-level variant posterior probabilities and L2G predictions
        - Present publication context and variant consequences for a locus

        **When not to use**
        - Listing multiple loci (use `get_study_credible_sets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `study_locus_id` (`str`): Identifier such as `"GCST90002357_chr7:140419283-140624564"`.

        **Returns**
        - `Dict[str, Any]`: `{"credibleSet": {"studyLocusId": str, "studyId": str, "confidence": float, "variant": {...}, "l2GPredictions": {...}, ...}}`.

        **Errors**
        - GraphQL/network exceptions bubble up.

        **Example**
        ```python
        study_api = StudyApi()
        locus = await study_api.get_credible_set_by_id(client, "GCST90002357_chr7:140419283-140624564")
        print(locus["credibleSet"]["variant"]["id"])
        ```
        """
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

    async def get_credible_set_colocalisation(
        self,
        client: OpenTargetsClient,
        study_locus_id: str,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Retrieve colocalisation results for a credible set.

        **When to use**
        - Identify GWAS-GWAS or GWAS-molQTL overlapping credible sets
        - Find shared causal variants between traits using COLOC or eCAVIAR methods
        - Prioritise causal genes by linking GWAS signals to eQTL/pQTL evidence

        **When not to use**
        - Fetching credible set metadata without colocalisation (use `get_credible_set_by_id`)
        - Listing all credible sets for a study (use `get_study_credible_sets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `study_locus_id` (`str`): Credible set identifier.
        - `page_index` (`int`): Zero-based page (default 0).
        - `page_size` (`int`): Number of colocalisation rows per page (default 10).

        **Returns**
        - `Dict[str, Any]`: `{"credibleSet": {"studyLocusId": str, "colocalisation": {"count": int, "rows": [{"colocalisationMethod": str, "h4": float, "otherStudyLocus": {...}}, ...]}}}`.

        **Errors**
        - GraphQL/network exceptions bubble up.

        **Example**
        ```python
        study_api = StudyApi()
        coloc = await study_api.get_credible_set_colocalisation(client, "GCST90002357_1_154453788_C_T")
        for row in coloc["credibleSet"]["colocalisation"]["rows"]:
            print(row["colocalisationMethod"], row["h4"])
        ```
        """
        graphql_query = """
        query CredibleSetColocalisation($studyLocusId: String!, $pageIndex: Int!, $pageSize: Int!) {
            credibleSet(studyLocusId: $studyLocusId) {
                studyLocusId
                studyId
                studyType
                chromosome
                position
                variant {
                    id
                    rsIds
                }
                study {
                    id
                    traitFromSource
                }
                colocalisation(page: {index: $pageIndex, size: $pageSize}) {
                    count
                    rows {
                        leftStudyLocusId
                        rightStudyLocusId
                        rightStudyType
                        chromosome
                        colocalisationMethod
                        numberColocalisingVariants
                        h3
                        h4
                        clpp
                        betaRatioSignAverage
                        otherStudyLocus {
                            studyLocusId
                            studyId
                            studyType
                            variant {
                                id
                                rsIds
                            }
                            study {
                                id
                                traitFromSource
                                target {
                                    id
                                    approvedSymbol
                                }
                                biosample {
                                    biosampleId
                                    biosampleName
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {
            "studyLocusId": study_locus_id,
            "pageIndex": page_index,
            "pageSize": page_size
        })

    async def get_credible_sets(
        self,
        client: OpenTargetsClient,
        study_locus_ids: Optional[List[str]] = None,
        study_ids: Optional[List[str]] = None,
        variant_ids: Optional[List[str]] = None,
        study_types: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Query credible sets with flexible filtering options.

        **When to use**
        - Search credible sets by multiple criteria (study IDs, variant IDs, regions)
        - Filter by study type (gwas, eqtl, pqtl, sqtl, tuqtl, sceqtl)
        - Query by genomic region for positional analyses

        **When not to use**
        - Fetching a single credible set by ID (use `get_credible_set_by_id`)
        - Listing credible sets for a specific study (use `get_study_credible_sets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `study_locus_ids` (`Optional[List[str]]`): Filter by specific credible set IDs.
        - `study_ids` (`Optional[List[str]]`): Filter by study identifiers.
        - `variant_ids` (`Optional[List[str]]`): Filter by variant identifiers.
        - `study_types` (`Optional[List[str]]`): Filter by study type (e.g., `["gwas", "eqtl"]`).
        - `regions` (`Optional[List[str]]`): Filter by genomic regions (e.g., `["1:154000000-155000000"]`).
        - `page_index` (`int`): Zero-based page (default 0).
        - `page_size` (`int`): Number of rows per page (default 10).

        **Returns**
        - `Dict[str, Any]`: `{"credibleSets": {"count": int, "rows": [{"studyLocusId": str, "studyId": str, "variant": {...}, ...}]}}`.

        **Errors**
        - GraphQL/network exceptions propagate.

        **Example**
        ```python
        study_api = StudyApi()
        # Find all eQTL credible sets for a variant
        results = await study_api.get_credible_sets(
            client,
            variant_ids=["1_154453788_C_T"],
            study_types=["eqtl"]
        )
        print(results["credibleSets"]["count"])
        ```
        """
        graphql_query = """
        query CredibleSets(
            $studyLocusIds: [String!],
            $studyIds: [String!],
            $variantIds: [String!],
            $studyTypes: [StudyTypeEnum!],
            $regions: [String!],
            $pageIndex: Int!,
            $pageSize: Int!
        ) {
            credibleSets(
                studyLocusIds: $studyLocusIds,
                studyIds: $studyIds,
                variantIds: $variantIds,
                studyTypes: $studyTypes,
                regions: $regions,
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
                    locusStart
                    locusEnd
                    beta
                    zScore
                    pValueMantissa
                    pValueExponent
                    standardError
                    credibleSetIndex
                    credibleSetlog10BF
                    finemappingMethod
                    confidence
                    purityMeanR2
                    purityMinR2
                    effectAlleleFrequencyFromSource
                    sampleSize
                    qualityControls
                    variant {
                        id
                        rsIds
                        chromosome
                        position
                    }
                    study {
                        id
                        traitFromSource
                        studyType
                        pubmedId
                        publicationFirstAuthor
                        target {
                            id
                            approvedSymbol
                        }
                    }
                }
            }
        }
        """
        variables = {
            "studyLocusIds": study_locus_ids,
            "studyIds": study_ids,
            "variantIds": variant_ids,
            "studyTypes": study_types,
            "regions": regions,
            "pageIndex": page_index,
            "pageSize": page_size
        }
        # Remove None values
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

# src/opentargets_mcp/tools/variant.py
"""
Defines API methods and MCP tools related to 'Variant' entities in Open Targets.
"""
from typing import Any, Dict, List, Optional
from ..queries import OpenTargetsClient

class VariantApi:
    """
    Contains methods to query variant-specific data from the Open Targets GraphQL API.
    """

    async def get_variant_info(self, client: OpenTargetsClient, variant_id: str) -> Dict[str, Any]:
        """Retrieve core metadata and functional annotations for a variant.

        **When to use**
        - Confirm position, alleles, rsIDs, and HGVS nomenclature for a variant
        - Inspect consequences, transcript impacts, and variant effect scores
        - Provide foundational information before exploring evidence or associations

        **When not to use**
        - Searching for variant IDs from traits/diseases (use study or evidence tools)
        - Listing studies containing the variant (use `get_variant_credible_sets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `variant_id` (`str`): Identifier such as `"7_140453136_A_T"`.

        **Returns**
        - `Dict[str, Any]`: `{"variant": {"id": str, "variantDescription": str, "chromosome": str, "position": int, "rsIds": [...], "transcriptConsequences": [...], ...}}`.

        **Errors**
        - GraphQL/network exceptions propagate via the client.

        **Example**
        ```python
        variant_api = VariantApi()
        variant = await variant_api.get_variant_info(client, "7_140453136_A_T")
        print(variant["variant"]["rsIds"])
        ```
        """
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
        """List credible sets that include a specific variant.

        **When to use**
        - Identify which fine-mapping studies implicate the variant
        - Filter credible sets by study types (e.g., GWAS, molecular traits)
        - Provide pagination for user exploration of multiple loci

        **When not to use**
        - Fetching study metadata (use study tools)
        - Retrieving variant pharmacogenomics or evidence (use respective tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `variant_id` (`str`): Variant identifier.
        - `study_types` (`Optional[List[str]]`): List of `StudyTypeEnum` values to filter by.
        - `page_index` (`int`): Zero-based page number (default 0).
        - `page_size` (`int`): Number of rows per page (default 10).

        **Returns**
        - `Dict[str, Any]`: `{"variant": {"id": str, "credibleSets": {"count": int, "rows": [{"studyLocusId": str, "studyId": str, "confidence": float, ...}, ...]}}}`.

        **Errors**
        - GraphQL/network exceptions bubble up.

        **Example**
        ```python
        variant_api = VariantApi()
        credible_sets = await variant_api.get_variant_credible_sets(client, "7_140453136_A_T")
        print(credible_sets["variant"]["credibleSets"]["rows"][0]["studyId"])
        ```
        """
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
        """Retrieve pharmacogenomic annotations for a variant.

        **When to use**
        - Surface genotype–phenotype relationships relevant to drug response
        - Provide evidence level and datasource for pharmacogenomic findings
        - Explore associated targets and drugs for personalised medicine use cases

        **When not to use**
        - Listing fine-mapping evidence (use `get_variant_credible_sets`)
        - Accessing generic evidence (use `get_variant_evidences`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `variant_id` (`str`): Variant identifier.
        - `page_index` (`int`): Zero-based page (default 0).
        - `page_size` (`int`): Number of pharmacogenomic rows (default 10).

        **Returns**
        - `Dict[str, Any]`: `{"variant": {"id": str, "rsIds": [...], "pharmacogenomics": [{"variantId": str, "genotype": str, "phenotypeText": str, "pgxCategory": str, "evidenceLevel": str, "drugs": [...], ...}, ...]}}`.

        **Errors**
        - GraphQL/network exceptions propagate.

        **Example**
        ```python
        variant_api = VariantApi()
        pgx = await variant_api.get_variant_pharmacogenomics(client, "7_140453136_A_T")
        print(pgx["variant"]["pharmacogenomics"][0]["phenotypeText"])
        ```
        """
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
        """Retrieve evidence strings linking a variant to targets or diseases.

        **When to use**
        - Audit supporting evidence for variant-level associations
        - Filter by datasource (e.g., `["gene_burden", "ot_differential_expression"]`)
        - Page through evidence rows using the cursor interface

        **When not to use**
        - Focusing on pharmacogenomics or study credible sets (use other variant APIs)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `variant_id` (`str`): Variant identifier.
        - `datasource_ids` (`Optional[List[str]]`): Limit evidence to specific datasources.
        - `size` (`int`): Number of evidence rows per page (default 10).
        - `cursor` (`Optional[str]`): Pagination cursor from a previous request.

        **Returns**
        - `Dict[str, Any]`: `{"variant": {"evidences": {"count": int, "cursor": str, "rows": [{"id": str, "score": float, "target": {...}, "disease": {...}, ...}], ...}}}`.

        **Errors**
        - GraphQL/network exceptions bubble up through the client.

        **Example**
        ```python
        variant_api = VariantApi()
        evidences = await variant_api.get_variant_evidences(client, "7_140453136_A_T", size=5)
        print(evidences["variant"]["evidences"]["rows"][0]["datasourceId"])
        ```
        """
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
                        variantRsId
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

    async def get_variant_intervals(
        self,
        client: OpenTargetsClient,
        variant_id: str,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Retrieve enhancer-to-gene (E2G) predictions overlapping a variant.

        **When to use**
        - Identify regulatory regions (enhancers/promoters) that overlap a variant location
        - Link variants to predicted target genes via ENCODE-rE2G model
        - Explore tissue/cell-type specific regulatory evidence for variant interpretation

        **When not to use**
        - Fetching variant functional consequences (use `get_variant_info`)
        - Looking for GWAS/QTL associations (use `get_variant_credible_sets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `variant_id` (`str`): Variant identifier (e.g., `"1_154453788_C_T"`).
        - `page_index` (`int`): Zero-based page (default 0).
        - `page_size` (`int`): Number of interval rows per page (default 10).

        **Returns**
        - `Dict[str, Any]`: `{"variant": {"id": str, "intervals": {"count": int, "rows": [{"intervalType": str, "score": float, "target": {...}, "biosampleName": str, ...}]}}}`.

        **Errors**
        - GraphQL/network exceptions propagate.

        **Example**
        ```python
        variant_api = VariantApi()
        intervals = await variant_api.get_variant_intervals(client, "1_154453788_C_T")
        for row in intervals["variant"]["intervals"]["rows"]:
            print(row["target"]["approvedSymbol"], row["biosampleName"], row["score"])
        ```
        """
        graphql_query = """
        query VariantIntervals($variantId: String!, $pageIndex: Int!, $pageSize: Int!) {
            variant(variantId: $variantId) {
                id
                rsIds
                chromosome
                position
                intervals(page: {index: $pageIndex, size: $pageSize}) {
                    count
                    rows {
                        chromosome
                        start
                        end
                        intervalType
                        score
                        resourceScore {
                            name
                            value
                        }
                        datasourceId
                        pmid
                        studyId
                        distanceToTss
                        biosampleName
                        biosample {
                            biosampleId
                            biosampleName
                            description
                        }
                        target {
                            id
                            approvedSymbol
                            approvedName
                            biotype
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {
            "variantId": variant_id,
            "pageIndex": page_index,
            "pageSize": page_size
        })

    async def get_variant_protein_coordinates(
        self,
        client: OpenTargetsClient,
        variant_id: str,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Retrieve protein-level consequences for a variant.

        **When to use**
        - Map variants to amino acid changes in protein products
        - Identify protein positions affected by coding variants
        - Support structural biology analyses linking variants to protein function

        **When not to use**
        - Fetching transcript-level consequences (use `get_variant_info`)
        - Looking for regulatory region overlaps (use `get_variant_intervals`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `variant_id` (`str`): Variant identifier (e.g., `"7_140753336_A_T"`).
        - `page_index` (`int`): Zero-based page (default 0).
        - `page_size` (`int`): Number of rows per page (default 10).

        **Returns**
        - `Dict[str, Any]`: `{"variant": {"id": str, "proteinCodingCoordinates": {"count": int, "rows": [...]}}}`.

        **Errors**
        - GraphQL/network exceptions propagate.

        **Example**
        ```python
        variant_api = VariantApi()
        coords = await variant_api.get_variant_protein_coordinates(client, "7_140753336_A_T")
        print(coords["variant"]["proteinCodingCoordinates"]["count"])
        ```
        """
        graphql_query = """
        query VariantProteinCoordinates($variantId: String!, $pageIndex: Int!, $pageSize: Int!) {
            variant(variantId: $variantId) {
                id
                rsIds
                chromosome
                position
                proteinCodingCoordinates(page: {index: $pageIndex, size: $pageSize}) {
                    count
                    rows {
                        aminoAcidPosition
                        referenceAminoAcid
                        alternateAminoAcid
                        variantEffect
                        uniprotAccessions
                        therapeuticAreas
                        datasources {
                            datasourceId
                            datasourceNiceName
                            datasourceCount
                        }
                        variantConsequences {
                            id
                            label
                        }
                        diseases {
                            id
                            name
                        }
                        target {
                            id
                            approvedSymbol
                            approvedName
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
        return await client._query(graphql_query, {
            "variantId": variant_id,
            "pageIndex": page_index,
            "pageSize": page_size
        })

# src/opentargets_mcp/tools/disease.py
"""
Defines API methods and MCP tools related to 'Disease' entities in Open Targets.
"""
from typing import Any, Dict, List, Optional
from ..queries import OpenTargetsClient # Relative import
from ..utils import select_fields

class DiseaseApi:
    """
    Contains methods to query disease-specific data from the Open Targets GraphQL API.
    """

    async def get_disease_info(
        self,
        client: OpenTargetsClient,
        efo_id: str,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve core metadata for an Open Targets disease entity.

        **When to use**
        - Confirm that an EFO identifier corresponds to the expected disease concept
        - Display synonyms, therapeutic areas, or descriptions prior to deeper analysis
        - Provide canonical naming before fetching associations or evidence

        **When not to use**
        - Discovering the correct EFO ID from a name (use `search_entities`)
        - Listing targets linked to the disease (use `get_disease_associated_targets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client instance.
        - `efo_id` (`str`): Disease identifier such as `"EFO_0003884"` or `"MONDO_0007254"`.
        - `fields` (`Optional[List[str]]`): Optional dot-paths to filter the response payload.

        **Returns**
        - `Dict[str, Any]`: `{ "disease": {"id": str, "name": str, "description": str, "synonyms": [...], "therapeuticAreas": [...], "dbXRefs": [...] } }`.

        **Errors**
        - GraphQL or network exceptions are propagated by `OpenTargetsClient`.

        **Example**
        ```python
        disease_api = DiseaseApi()
        details = await disease_api.get_disease_info(client, "EFO_0003884")
        print(details["disease"]["name"])
        ```
        """
        graphql_query = """
        query DiseaseInfo($efoId: String!) {
            disease(efoId: $efoId) {
                id
                name
                description
                synonyms { # DiseaseSynonym
                    relation
                    terms
                }
                therapeuticAreas { # OntologyTerm
                     id
                     name
                }
                dbXRefs # list of strings
                # Removed 'ontology' field as it's not directly on Disease type as structured before.
                # Ontology information is typically within therapeuticAreas or implied by EFO structure.
            }
        }
        """
        result = await client._query(graphql_query, {"efoId": efo_id})
        return select_fields(result, fields)

    async def get_disease_associated_targets(
        self,
        client: OpenTargetsClient,
        efo_id: str,
        fields: Optional[List[str]] = None,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """List targets associated with a disease, including evidence scores.

        **When to use**
        - Prioritise targets for a disease program using Open Targets association scores
        - Drive UI components that show paginated association tables
        - Feed downstream analyses with target IDs linked to a disease

        **When not to use**
        - Exploring disease phenotypes (use `get_disease_phenotypes`)
        - Investigating evidence at the variant or study level (use evidence/study tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `efo_id` (`str`): Disease identifier.
        - `fields` (`Optional[List[str]]`): Optional dot-paths to filter the response payload.
        - `page_index` (`int`): Zero-based page for pagination (default 0).
        - `page_size` (`int`): Number of associations per page (default 10).

        **Returns**
        - `Dict[str, Any]`: Payload `{"disease": {"id": str, "name": str, "associatedTargets": {"count": int, "rows": [{"target": {...}, "score": float, "datatypeScores": [...]}, ...]}}}`.

        **Errors**
        - Propagates GraphQL/network failures.

        **Example**
        ```python
        disease_api = DiseaseApi()
        associations = await disease_api.get_disease_associated_targets(client, "EFO_0003884", page_size=5)
        for row in associations["disease"]["associatedTargets"]["rows"]:
            print(row["target"]["approvedSymbol"], row["score"])
        ```
        """
        graphql_query = """
        query DiseaseAssociatedTargets($efoId: String!, $pageIndex: Int!, $pageSize: Int!) {
            disease(efoId: $efoId) {
                id
                name
                associatedTargets(page: {index: $pageIndex, size: $pageSize}) {
                    count
                    rows { # TargetDiseaseAssociation
                        target { # Target
                            id
                            approvedSymbol
                            approvedName
                            biotype
                        }
                        score # Overall association score
                        datatypeScores { # AssociationScore
                            id # datasourceId
                            score
                        }
                    }
                }
            }
        }
        """
        result = await client._query(graphql_query, {"efoId": efo_id, "pageIndex": page_index, "pageSize": page_size})
        return select_fields(result, fields)

    async def get_disease_known_drugs(
        self,
        client: OpenTargetsClient,
        efo_id: str,
        size: int = 10,
        cursor: Optional[str] = None,
        free_text_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve drugs with investigational or approved indications for a disease.

        **When to use**
        - Answer "What drugs treat X disease?" questions
        - Identify therapeutic options including clinical trial candidates
        - Explore mechanism of action data for disease-drug relationships

        **When not to use**
        - Finding diseases for a drug (use `get_drug_linked_diseases`)
        - Exploring target associations (use `get_disease_associated_targets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `efo_id` (`str`): Disease identifier such as `"EFO_0000583"`.
        - `size` (`int`): Number of drug rows to return (default 10).
        - `cursor` (`Optional[str]`): Pagination cursor from a previous call.
        - `free_text_query` (`Optional[str]`): Filter results by a free-text query.

        **Returns**
        - `Dict[str, Any]`: `{"disease": {"id": str, "name": str, "knownDrugs": {"count": int, "rows": [{"drug": {...}, "phase": int, "status": str, ...}]}}}`.

        **Errors**
        - GraphQL/network exceptions propagate via the client.

        **Example**
        ```python
        disease_api = DiseaseApi()
        drugs = await disease_api.get_disease_known_drugs(client, "EFO_0000583", size=5)
        for row in drugs["disease"]["knownDrugs"]["rows"]:
            print(row["drug"]["name"], row["phase"])
        ```
        """
        graphql_query = """
        query DiseaseKnownDrugs($efoId: String!, $size: Int!, $cursor: String, $freeTextQuery: String) {
            disease(efoId: $efoId) {
                id
                name
                knownDrugs(size: $size, cursor: $cursor, freeTextQuery: $freeTextQuery) {
                    count
                    cursor
                    rows {
                        drugId
                        targetId
                        drug {
                            id
                            name
                            drugType
                            maximumClinicalTrialPhase
                            isApproved
                        }
                        mechanismOfAction
                        target {
                            id
                            approvedSymbol
                        }
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
        variables = {
            "efoId": efo_id,
            "size": size,
            "cursor": cursor,
            "freeTextQuery": free_text_query,
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

    async def get_disease_ontology(
        self,
        client: OpenTargetsClient,
        efo_id: str,
    ) -> Dict[str, Any]:
        """Retrieve ontology structure for a disease including parents, children, and ancestors.

        **When to use**
        - Navigate disease hierarchy ("What are the subtypes of cancer?")
        - Find parent therapeutic areas for a specific disease
        - Explore disease relationships in the EFO ontology

        **When not to use**
        - Getting disease metadata (use `get_disease_info`)
        - Finding associated targets (use `get_disease_associated_targets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `efo_id` (`str`): Disease identifier such as `"EFO_0000270"`.

        **Returns**
        - `Dict[str, Any]`: `{"disease": {"id": str, "name": str, "parents": [...], "children": [...], "ancestors": [...], "descendants": [...], "therapeuticAreas": [...], "isTherapeuticArea": bool}}`.

        **Errors**
        - GraphQL/network exceptions propagate via the client.
        """
        graphql_query = """
        query DiseaseOntology($efoId: String!) {
            disease(efoId: $efoId) {
                id
                name
                description
                isTherapeuticArea
                parents {
                    id
                    name
                }
                children {
                    id
                    name
                }
                ancestors
                descendants
                therapeuticAreas {
                    id
                    name
                }
            }
        }
        """
        return await client._query(graphql_query, {"efoId": efo_id})

    async def get_disease_literature_occurrences(
        self,
        client: OpenTargetsClient,
        efo_id: str,
        additional_entity_ids: Optional[List[str]] = None,
        start_year: Optional[int] = None,
        start_month: Optional[int] = None,
        end_year: Optional[int] = None,
        end_month: Optional[int] = None,
        cursor: Optional[str] = None,
        size: Optional[int] = 20,
    ) -> Dict[str, Any]:
        """Return literature co-occurrence records mentioning a disease.

        **When to use**
        - Find publications discussing a specific disease
        - Filter by co-mentioned entities (e.g., disease + target)
        - Provide publication timelines with year filters

        **When not to use**
        - Looking for evidence data (use evidence tools)
        - Finding disease-target associations (use `get_disease_associated_targets`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `efo_id` (`str`): Disease identifier.
        - `additional_entity_ids` (`Optional[List[str]]`): Co-filter on additional entities.
        - `start_year` / `end_year` (`Optional[int]`): Restrict by publication year.
        - `start_month` / `end_month` (`Optional[int]`): Optional month filters.
        - `cursor` (`Optional[str]`): Pagination cursor.
        - `size` (`Optional[int]`): Max rows to return (default 20).

        **Returns**
        - `Dict[str, Any]`: `{"disease": {"literatureOcurrences": {"count": int, "rows": [{"pmid": str, "pmcid": str, "publicationDate": str}, ...]}}}`.
        """
        graphql_query = """
        query DiseaseLiteratureOcurrences(
            $efoId: String!,
            $additionalIds: [String!],
            $startYear: Int,
            $startMonth: Int,
            $endYear: Int,
            $endMonth: Int,
            $cursor: String
        ) {
            disease(efoId: $efoId) {
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
        variables = {
            "efoId": efo_id,
            "additionalIds": additional_entity_ids,
            "startYear": start_year,
            "startMonth": start_month,
            "endYear": end_year,
            "endMonth": end_month,
            "cursor": cursor,
        }
        variables = {k: v for k, v in variables.items() if v is not None}

        result = await client._query(graphql_query, variables)

        if size is not None and isinstance(size, int) and size >= 0 and result.get("disease"):
            literature = result["disease"].get("literatureOcurrences")
            if literature and isinstance(literature, dict):
                rows = literature.get("rows")
                if isinstance(rows, list):
                    literature["rows"] = rows[:size]

        return result

    async def get_disease_similar_entities(
        self,
        client: OpenTargetsClient,
        efo_id: str,
        threshold: Optional[float] = 0.5,
        size: int = 10,
        entity_names: Optional[List[str]] = None,
        additional_entity_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Find semantically similar diseases based on PubMed embeddings.

        **When to use**
        - Expand disease scope ("What diseases are similar to asthma?")
        - Find related conditions for comparative analysis
        - Discover diseases with overlapping literature profiles

        **When not to use**
        - Finding disease subtypes (use `get_disease_ontology`)
        - Looking for comorbidities (this is semantic similarity, not clinical)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `efo_id` (`str`): Disease identifier.
        - `threshold` (`Optional[float]`): Minimum similarity score (0-1), default 0.5.
        - `size` (`int`): Maximum similar diseases to return (default 10).
        - `entity_names` (`Optional[List[str]]`): Entity types to include; defaults to `["disease"]`.
        - `additional_entity_ids` (`Optional[List[str]]`): Additional entity IDs for similarity context.

        **Returns**
        - `Dict[str, Any]`: `{"disease": {"id": str, "name": str, "similarEntities": [{"score": float, "object": {"id": str, "name": str}}, ...]}}`.
        """
        graphql_query = """
        query DiseaseSimilarEntities(
            $efoId: String!,
            $threshold: Float,
            $size: Int!,
            $entityNames: [String!],
            $additionalIds: [String!]
        ) {
            disease(efoId: $efoId) {
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
                        ... on Disease {
                            id
                            name
                            description
                            therapeuticAreas {
                                id
                                name
                            }
                        }
                    }
                }
            }
        }
        """
        variables = {
            "efoId": efo_id,
            "threshold": threshold,
            "size": size,
            "entityNames": entity_names or ["disease"],
            "additionalIds": additional_entity_ids,
        }
        variables = {k: v for k, v in variables.items() if v is not None}
        return await client._query(graphql_query, variables)

    async def get_disease_phenotypes(
        self,
        client: OpenTargetsClient,
        efo_id: str,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Fetch HPO phenotype annotations linked to a disease.

        **When to use**
        - Summarise phenotypic manifestations associated with a disease for downstream reporting
        - Obtain HPO terms to bridge to phenotype-driven tools
        - Investigate supporting evidence metadata (frequency, modifiers, onset)

        **When not to use**
        - Accessing genetic associations or targets (see the association/evidence tools)
        - Discovering diseases from phenotype terms (use search tools first)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `efo_id` (`str`): Disease identifier.
        - `page_index` (`int`): Zero-based page (default 0).
        - `page_size` (`int`): Number of phenotype rows to retrieve (default 10).

        **Returns**
        - `Dict[str, Any]`: Structure `{"disease": {"id": str, "name": str, "phenotypes": {"count": int, "rows": [{"phenotypeHPO": {...}, "phenotypeEFO": {...}, "evidence": [...]}, ...]}}}`.

        **Errors**
        - GraphQL query or transport errors are raised by the client.

        **Example**
        ```python
        disease_api = DiseaseApi()
        phenotypes = await disease_api.get_disease_phenotypes(client, "EFO_0003884")
        first_hpo = phenotypes["disease"]["phenotypes"]["rows"][0]["phenotypeHPO"]
        print(first_hpo["id"], first_hpo["name"])
        ```
        """
        graphql_query = """
        query DiseasePhenotypes($efoId: String!, $pageIndex: Int!, $pageSize: Int!) {
            disease(efoId: $efoId) {
                id
                name
                phenotypes(page: {index: $pageIndex, size: $pageSize}) { # Paginated DiseasePhenotype
                    count
                    rows { # DiseasePhenotype
                        phenotypeHPO { # OntologyTerm (HPO)
                            id
                            name
                            description
                        }
                        phenotypeEFO { # OntologyTerm (EFO, if available)
                            id
                            name
                        }
                        evidence { # DiseasePhenotypeEvidence (Array)
                            aspect 
                            bioCuration 
                            diseaseFromSource
                            diseaseFromSourceId
                            evidenceType 
                            frequency # Corrected: Now a String, not an object
                            # modifiers # Assuming modifiers is also a String or list of Strings based on schema
                            # onset # Assuming onset is also a String or list of Strings based on schema
                            # If modifiers and onset are objects, they need specific subfields.
                            # For now, let's assume they are simple strings if the API returns them as such.
                            # If they are objects, the API error would guide further correction.
                            # Based on schema, DiseasePhenotypeEvidence has:
                            # frequency: String (e.g. "HP:0040283")
                            # modifiers: [OntologyTerm!] (so this should be modifiers { id name })
                            # onset: [OntologyTerm!] (so this should be onset { id name })
                            modifiers { id name } # Corrected based on schema
                            onset { id name }     # Corrected based on schema
                            qualifierNot 
                            references 
                            resource 
                            sex
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"efoId": efo_id, "pageIndex": page_index, "pageSize": page_size})

    async def get_disease_otar_projects(self, client: OpenTargetsClient, efo_id: str) -> Dict[str, Any]:
        """List Open Targets Associated Research (OTAR) projects linked to a disease.

        **When to use**
        - Identify collaborative projects focused on a disease of interest
        - Provide contextual information about PPP involvement or project status
        - Surface references to OTAR programmes in user interfaces

        **When not to use**
        - Looking for therapeutic targets or clinical evidence (use association/drug tools)
        - Searching for diseases related to a project (search for the project code instead)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `efo_id` (`str`): Disease identifier.

        **Returns**
        - `Dict[str, Any]`: `{ "disease": {"id": str, "name": str, "otarProjects": [{"otarCode": str, "projectName": str, "status": str, "reference": str, "integratesInPPP": bool}, ...]} }`.

        **Errors**
        - GraphQL/network errors bubble up through the client.

        **Example**
        ```python
        disease_api = DiseaseApi()
        projects = await disease_api.get_disease_otar_projects(client, "EFO_0003884")
        print([proj["projectName"] for proj in projects["disease"]["otarProjects"]])
        ```
        """
        graphql_query = """
        query DiseaseOTARProjects($efoId: String!) {
            disease(efoId: $efoId) {
                id
                name
                otarProjects { # Array of OTARProject
                    otarCode
                    projectName
                    status
                    reference
                    integratesInPPP # Public Private Partnership
                }
            }
        }
        """
        return await client._query(graphql_query, {"efoId": efo_id})

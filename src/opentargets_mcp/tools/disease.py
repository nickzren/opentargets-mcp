# src/opentargets_mcp/tools/disease.py
"""
Defines API methods and MCP tools related to 'Disease' entities in Open Targets.
"""
from typing import Any, Dict
from ..queries import OpenTargetsClient # Relative import

class DiseaseApi:
    """
    Contains methods to query disease-specific data from the Open Targets GraphQL API.
    """

    async def get_disease_info(self, client: OpenTargetsClient, efo_id: str) -> Dict[str, Any]:
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
        return await client._query(graphql_query, {"efoId": efo_id})

    async def get_disease_associated_targets(
        self,
        client: OpenTargetsClient,
        efo_id: str,
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
        return await client._query(graphql_query, {"efoId": efo_id, "pageIndex": page_index, "pageSize": page_size})

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

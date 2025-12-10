# src/opentargets_mcp/tools/meta.py
"""
Defines API methods and MCP tools for metadata and utility functions in Open Targets.
"""
from typing import Any, Dict, List, Optional
from ..queries import OpenTargetsClient

class MetaApi:
    """
    Contains methods for metadata and utility queries.
    """

    async def get_api_metadata(self, client: OpenTargetsClient) -> Dict[str, Any]:
        """Return Open Targets Platform release metadata.

        **When to use**
        - Validate that your MCP server targets the expected API release
        - Surface release notes or data provenance alongside downstream analyses
        - Troubleshoot mismatches between local cache versions and the live platform

        **When not to use**
        - Retrieving disease, target, or drug content (use the corresponding domain tool instead)
        - Listing data sources (see `get_association_datasources`)

        **Parameters**
        - `client` (`OpenTargetsClient`): Asynchronous GraphQL client configured for the Open Targets Platform.

        **Returns**
        - `Dict[str, Any]`: GraphQL payload shaped as `{"meta": {"name": str, "apiVersion": {"x": int, "y": int, "z": int}, "dataVersion": {"year": int, "month": int, "iteration": int}}}`.

        **Errors**
        - Propagates `OpenTargetsClient` GraphQL errors if the API call fails.
        - Underlying network exceptions from `aiohttp` bubble up unchanged.

        **Example**
        ```python
        meta_api = MetaApi()
        version_info = await meta_api.get_api_metadata(client)
        print(version_info["meta"]["dataVersion"]["year"])
        ```
        """
        graphql_query = """
        query ApiMetadata {
            meta {
                name
                apiVersion {
                    x
                    y
                    z
                }
                dataVersion {
                    year
                    month
                    iteration
                }
            }
        }
        """
        return await client._query(graphql_query)

    async def get_association_datasources(self, client: OpenTargetsClient) -> Dict[str, Any]:
        """List sources contributing target–disease association evidence.

        **When to use**
        - Build UI filters keyed by association datasource or datatype
        - Explain provenance for evidence supporting a therapeutic hypothesis
        - Verify that a datasource you rely on exists in the current release

        **When not to use**
        - Fetching the actual association rows (use `get_target_associated_diseases` or disease equivalents)
        - Exploring protein–protein interaction resources (use `get_interaction_resources`)

        **Parameters**
        - `client` (`OpenTargetsClient`): Active GraphQL client session.

        **Returns**
        - `Dict[str, Any]`: Payload shaped as `{"associationDatasources": [{"datasource": str, "datatype": str}, ...]}`.

        **Errors**
        - Raises the underlying client exception if the GraphQL request fails.
        - Network issues from the HTTP layer are propagated.

        **Example**
        ```python
        meta_api = MetaApi()
        datasources = await meta_api.get_association_datasources(client)
        print({item["datasource"] for item in datasources["associationDatasources"]})
        ```
        """
        graphql_query = """
        query AssociationDatasources {
            associationDatasources {
                datasource
                datatype
            }
        }
        """
        return await client._query(graphql_query)

    async def get_interaction_resources(self, client: OpenTargetsClient) -> Dict[str, Any]:
        """Enumerate interaction databases integrated into Open Targets.

        **When to use**
        - Audit which molecular interaction repositories underpin interaction-aware tools
        - Display citation information alongside interaction results
        - Confirm database versions before comparing across releases

        **When not to use**
        - Downloading individual interaction edges (use target interaction tools for that)
        - Exploring association datasources (see `get_association_datasources`)

        **Parameters**
        - `client` (`OpenTargetsClient`): Active GraphQL transport.

        **Returns**
        - `Dict[str, Any]`: Structure `{"interactionResources": [{"sourceDatabase": str, "databaseVersion": str}, ...]}`.

        **Errors**
        - GraphQL or HTTP failures are re-raised from the underlying client.

        **Example**
        ```python
        meta_api = MetaApi()
        resources = await meta_api.get_interaction_resources(client)
        for entry in resources["interactionResources"]:
            print(entry["sourceDatabase"], entry["databaseVersion"])
        ```
        """
        graphql_query = """
        query InteractionResources {
            interactionResources {
                sourceDatabase
                databaseVersion
            }
        }
        """
        return await client._query(graphql_query)

    async def get_gene_ontology_terms(self, client: OpenTargetsClient, go_ids: List[str]) -> Dict[str, Any]:
        """Resolve Gene Ontology identifiers to human-readable labels.

        **When to use**
        - Validate GO identifiers returned from other tools before display
        - Enrich reports with GO term names without leaving the MCP workflow
        - Build mappings between GO IDs and strings for downstream annotation

        **When not to use**
        - Discovering GO IDs from free text (use `search_entities` instead)
        - Listing targets annotated to a GO term (use target biology tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client instance.
        - `go_ids` (`List[str]`): One or more identifiers such as `"GO:0006915"`. Provide 1–50 IDs per call for best performance.

        **Returns**
        - `Dict[str, Any]`: Response shaped as `{"geneOntologyTerms": [{"id": str, "name": str}, ...]}`; missing IDs result in an empty list entry.

        **Errors**
        - GraphQL and network errors are surfaced directly from `OpenTargetsClient`.

        **Example**
        ```python
        meta_api = MetaApi()
        terms = await meta_api.get_gene_ontology_terms(client, ["GO:0005515"])
        print(terms["geneOntologyTerms"][0]["name"])
        ```
        """
        graphql_query = """
        query GeneOntologyTerms($goIds: [String!]!) {
            geneOntologyTerms(goIds: $goIds) {
                id
                name
            }
        }
        """
        return await client._query(graphql_query, {"goIds": go_ids})

    async def map_ids(
        self,
        client: OpenTargetsClient,
        query_terms: List[str],
        entity_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Map free-text terms to canonical Open Targets identifiers.

        **When to use**
        - Translate user input (gene symbols, disease names, compound aliases) into IDs used by other tools
        - Provide disambiguation suggestions when a search term matches multiple entities
        - Pre-populate downstream calls (e.g., pick the highest scoring target ID before fetching associations)

        **When not to use**
        - Performing fuzzy search with pagination or scoring (use `search_entities`)
        - Restricting to a single entity type that already matches your identifier (call the specific tool directly)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `query_terms` (`List[str]`): One or more free-text values such as `["BRAF", "melanoma", "rs12345"]`.
        - `entity_names` (`Optional[List[str]]`): Optional subset of entity types (`"target"`, `"disease"`, `"drug"`, `"variant"`, `"study"`) to consider; defaults to target, disease, and drug.

        **Returns**
        - `Dict[str, Any]`: GraphQL response `{"mapIds": {"total": int, "mappings": [...], "aggregations": {...}}}` where each mapping includes candidate hits with scores and entity metadata.

        **Errors**
        - Propagates client/network exceptions from `OpenTargetsClient`.

        **Example**
        ```python
        meta_api = MetaApi()
        resolved = await meta_api.map_ids(client, ["BRAF"], entity_names=["target"])
        best = resolved["mapIds"]["mappings"][0]["hits"][0]
        print(best["id"], best["score"])
        ```
        """
        graphql_query = """
        query MapIds($queryTerms: [String!]!, $entityNames: [String!]) {
            mapIds(queryTerms: $queryTerms, entityNames: $entityNames) {
                total
                mappings {
                    term
                    hits {
                        id
                        name
                        entity
                        category
                        multiplier
                        prefixes
                        score
                        object {
                            __typename
                            ... on Target {
                                id
                                approvedSymbol
                                approvedName
                            }
                            ... on Disease {
                                id
                                name
                                description
                            }
                            ... on Drug {
                                id
                                name
                                drugType
                            }
                            ... on Variant {
                                id
                                chromosome
                                position
                                rsIds
                            }
                            ... on Study {
                                id
                                studyType
                                traitFromSource
                            }
                        }
                    }
                }
                aggregations {
                    total
                    entities {
                        name
                        total
                        categories {
                            name
                            total
                        }
                    }
                }
            }
        }
        """
        variables = {
            "queryTerms": query_terms,
            "entityNames": entity_names if entity_names else ["target", "disease", "drug", "variant", "study"]
        }
        return await client._query(graphql_query, variables)

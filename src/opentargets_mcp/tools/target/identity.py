# src/opentargets_mcp/tools/target/identity.py
"""
Defines API methods and MCP tools related to a target's identity and classification.
"""
from typing import Any, Dict
from ...queries import OpenTargetsClient

class TargetIdentityApi:
    """
    Contains methods to query a target's identity, classification, and cross-references.
    """
    async def get_target_info(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Retrieve core identity details for a target gene.

        **When to use**
        - Confirm a target’s approved symbol, name, biotype, and chromosomal location
        - Provide baseline information prior to showing associations or safety data
        - Obtain protein identifiers for integration with external resources

        **When not to use**
        - Searching for the correct Ensembl ID (use `search_entities`)
        - Listing target classes or cross-references (use dedicated tools below)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier (`"ENSG..."`).

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "approvedName": str, "biotype": str, "functionDescriptions": [...], "synonyms": [...], "genomicLocation": {...}, "proteinIds": [...]}}`.

        **Errors**
        - GraphQL/network errors propagate from the client.

        **Example**
        ```python
        target_api = TargetIdentityApi()
        target = await target_api.get_target_info(client, "ENSG00000157764")
        print(target["target"]["approvedSymbol"])
        ```
        """
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

    async def get_target_class(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Return ChEMBL target class annotations for a gene.

        **When to use**
        - Display molecular target class hierarchy levels (e.g., Kinase > Ser/Thr kinase)
        - Support filtering or grouping targets by ChEMBL classification
        - Provide context before exploring mechanism-of-action data

        **When not to use**
        - Needing expression, safety, or association data (use specialized tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "targetClass": [{"id": str, "label": str, "level": int}, ...]}}`.

        **Errors**
        - GraphQL/network exceptions are raised by the client.

        **Example**
        ```python
        target_api = TargetIdentityApi()
        classes = await target_api.get_target_class(client, "ENSG00000157764")
        print([cls["label"] for cls in classes["target"]["targetClass"]])
        ```
        """
        graphql_query = """
        query TargetClass($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                targetClass {
                    id
                    label
                    level
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_alternative_genes(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """List alternate gene symbols and database cross-references for a target.

        **When to use**
        - Map the target to other identifier systems (HGNC, RefSeq, UniProt)
        - Surface alias symbols for NLP or UI experiences
        - Inspect transcript IDs linked to the gene

        **When not to use**
        - Retrieving functional annotations or associations (use other target tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "alternativeGenes": [str, ...], "transcriptIds": [str, ...], "dbXrefs": [{"id": str, "source": str}, ...]}}`.

        **Errors**
        - Propagates client exceptions if the request fails.

        **Example**
        ```python
        target_api = TargetIdentityApi()
        aliases = await target_api.get_target_alternative_genes(client, "ENSG00000157764")
        print(aliases["target"]["dbXrefs"][:3])
        ```
        """
        graphql_query = """
        query TargetAlternativeGenes($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                alternativeGenes
                transcriptIds
                dbXrefs {
                    id
                    source
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

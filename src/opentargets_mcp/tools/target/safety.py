# src/opentargets_mcp/tools/target/safety.py
"""
Defines API methods and MCP tools related to target safety and tractability.
"""
from typing import Any, Dict
from ...exceptions import UpstreamQueryError
from ...queries import OpenTargetsClient

class TargetSafetyApi:
    """
    Contains methods to query target safety, tractability, and chemical probes.
    """
    async def get_target_safety_information(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Retrieve documented safety liabilities for a target.

        **When to use**
        - Surface known safety events associated with modulating a gene
        - Provide datasource provenance for safety liabilities (direction, dosing)
        - Inform risk assessments during target prioritisation

        **When not to use**
        - Reviewing tractability or probes (use dedicated tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "safetyLiabilities": [{"event": str, "eventId": str, "effects": [{"direction": str, "dosing": str}], "datasource": str}, ...]}}`.

        **Errors**
        - GraphQL/network errors propagate from the client.

        **Example**
        ```python
        safety_api = TargetSafetyApi()
        liabilities = await safety_api.get_target_safety_information(client, "ENSG00000157764")
        print(liabilities["target"]["safetyLiabilities"])
        ```
        """
        graphql_query = """
        query TargetSafety($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                safetyLiabilities {
                    event
                    eventId
                    effects {
                        direction
                        dosing
                    }
                    datasource
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_tractability(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Return tractability assessments across modalities for a target.

        **When to use**
        - Evaluate whether a target is tractable to antibodies, small molecules, or other modalities
        - Display tractability labels and scores in decision-support tools
        - Compare modalities during portfolio planning

        **When not to use**
        - Seeking detailed chemical probe information (use `get_target_chemical_probes`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "tractability": [{"modality": str, "value": float, "label": str}, ...]}}`.

        **Errors**
        - GraphQL/network failures bubble up.

        **Example**
        ```python
        safety_api = TargetSafetyApi()
        tractability = await safety_api.get_target_tractability(client, "ENSG00000157764")
        print(tractability["target"]["tractability"])
        ```
        """
        graphql_query = """
        query TargetTractability($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                tractability {
                    modality
                    value
                    label
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_chemical_probes(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """List available chemical probes and their quality metrics.

        **When to use**
        - Identify high-quality probes for experimental validation of a target
        - Provide probe metadata (origin, MOA, quality scores) to users
        - Link to external probe resources via URLs

        **When not to use**
        - Evaluating general tractability (use `get_target_tractability`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "chemicalProbes": [{"id": str, "isHighQuality": bool, "probesDrugsScore": float, ...}], ...}}`.

        **Errors**
        - GraphQL/network exceptions are propagated.

        **Example**
        ```python
        safety_api = TargetSafetyApi()
        probes = await safety_api.get_target_chemical_probes(client, "ENSG00000157764")
        print(probes["target"]["chemicalProbes"][0]["mechanismOfAction"])
        ```
        """
        graphql_query = """
        query TargetChemicalProbes($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                chemicalProbes {
                    id
                    control
                    drugId
                    isHighQuality
                    mechanismOfAction
                    origin
                    probesDrugsScore
                    scoreInCells
                    scoreInOrganisms
                    targetFromSourceId
                    urls { niceName, url }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

    async def get_target_tep(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Always raises: Target Enabling Package (TEP) data was removed from the Open Targets API (absent in API 26.9) and has no replacement.

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client (not used).
        - `ensembl_id` (`str`): Target identifier (not used).

        **Errors**
        - `UpstreamQueryError` on every call, without sending a request.
        """
        raise UpstreamQueryError(
            [
                "Target Enabling Package (TEP) data was removed from the Open "
                "Targets API (absent in API 26.9); there is no replacement."
            ]
        )

    async def get_target_prioritization(self, client: OpenTargetsClient, ensembl_id: str) -> Dict[str, Any]:
        """Return target prioritisation scores compiled across data sources.

        **When to use**
        - Present priority metrics alongside evidence summaries
        - Track key/value prioritisation fields for dashboarding
        - Compare prioritisation outputs between targets

        **When not to use**
        - Fetching association or evidence data (use other modules)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `ensembl_id` (`str`): Target identifier.

        **Returns**
        - `Dict[str, Any]`: `{"target": {"id": str, "approvedSymbol": str, "prioritisation": {"items": [{"key": str, "value": str}, ...]}}}`.

        **Errors**
        - GraphQL/network exceptions propagate through the client.

        **Example**
        ```python
        safety_api = TargetSafetyApi()
        priority = await safety_api.get_target_prioritization(client, "ENSG00000157764")
        print(priority["target"]["prioritisation"]["items"])
        ```
        """
        graphql_query = """
        query TargetPrioritisation($ensemblId: String!) {
            target(ensemblId: $ensemblId) {
                id
                approvedSymbol
                prioritisation {
                    items {
                        key
                        value
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"ensemblId": ensembl_id})

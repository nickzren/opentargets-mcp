# src/opentargets_mcp/tools/drug/identity.py
"""
Defines API methods and MCP tools related to a drug's identity and classification.
"""
from typing import Any, Dict
from ...queries import OpenTargetsClient

class DrugIdentityApi:
    """
    Contains methods to query a drug's identity and cross-references.
    """
    async def get_drug_info(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """Fetch identity, indication, and mechanism data for a drug.

        **When to use**
        - Verify that a ChEMBL ID aligns with the intended compound
        - Present mechanism of action, linked targets, or approval status to users
        - Seed follow-up calls (e.g., to association tools) with linked target IDs

        **When not to use**
        - Searching for the correct ChEMBL ID (use `search_entities` first)
        - Retrieving safety signals (use drug safety tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client session.
        - `chembl_id` (`str`): Identifier such as `"CHEMBL1862"`.

        **Returns**
        - `Dict[str, Any]`: `{ "drug": {"id": str, "name": str, "drugType": str, "isApproved": bool, "mechanismsOfAction": {...}, "indications": {...}, "linkedTargets": {...}, ...} }`.

        **Errors**
        - Raises GraphQL/network exceptions via `OpenTargetsClient`.

        **Example**
        ```python
        drug_api = DrugIdentityApi()
        drug = await drug_api.get_drug_info(client, "CHEMBL1862")
        print(drug["drug"]["name"], drug["drug"]["isApproved"])
        ```
        """
        graphql_query = """
        query DrugInfo($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                synonyms
                tradeNames
                drugType
                description
                isApproved
                hasBeenWithdrawn
                blackBoxWarning
                yearOfFirstApproval
                maximumClinicalTrialPhase
                mechanismsOfAction {
                    rows {
                       mechanismOfAction
                       targetName
                       targets {
                           id
                           approvedSymbol
                       }
                       actionType
                       references {
                           source
                           ids
                           urls
                       }
                    }
                }
                indications {
                    rows {
                        disease {
                            id
                            name
                            therapeuticAreas {id, name}
                        }
                        maxPhaseForIndication
                        references {
                            source
                            ids
                        }
                    }
                    count
                }
                linkedTargets {
                    rows {
                        id
                        approvedSymbol
                        biotype
                    }
                    count
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})

    async def get_drug_cross_references(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """Retrieve cross-database identifiers related to a drug.

        **When to use**
        - Link Open Targets drug records to external databases (DrugBank, PubChem, etc.)
        - Display alternate molecule hierarchies (parent/child) in interfaces
        - Prepare data integrations that require multiple identifier schemes

        **When not to use**
        - Fetching pharmacovigilance or safety details (use safety tools)
        - Getting indication information (use `get_drug_info`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `chembl_id` (`str`): Drug identifier.

        **Returns**
        - `Dict[str, Any]`: `{"drug": {"id": str, "name": str, "crossReferences": [{"source": str, "ids": [str, ...]}, ...], "parentMolecule": {...}, "childMolecules": [...]}}`.

        **Errors**
        - Propagates GraphQL/network failures.

        **Example**
        ```python
        drug_api = DrugIdentityApi()
        xrefs = await drug_api.get_drug_cross_references(client, "CHEMBL1862")
        print(xrefs["drug"]["crossReferences"])
        ```
        """
        graphql_query = """
        query DrugCrossReferences($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                synonyms
                crossReferences {
                    source
                    ids
                }
                parentMolecule {
                    id
                    name
                }
                childMolecules {
                    id
                    name
                    drugType
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})

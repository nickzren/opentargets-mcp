# src/opentargets_mcp/tools/drug/associations.py
"""
Defines API methods and MCP tools related to a drug's associations with other entities.
"""
from typing import Any, Dict
from ...queries import OpenTargetsClient

class DrugAssociationsApi:
    """
    Contains methods to query a drug's associations with diseases and targets.
    """
    async def get_drug_linked_diseases(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """List diseases connected to a drug across indications and mechanisms.

        **When to use**
        - Summarise a compound’s therapeutic footprint across disease areas
        - Populate UI components with known disease indications for a drug
        - Provide context before exploring disease-specific evidence

        **When not to use**
        - Retrieving detailed clinical trial evidence (use evidence tools)
        - Discovering drugs for a disease (use disease association tools instead)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `chembl_id` (`str`): Drug identifier.

        **Returns**
        - `Dict[str, Any]`: `{"drug": {"id": str, "name": str, "linkedDiseases": {"count": int, "rows": [{"id": str, "name": str, "therapeuticAreas": [...]}, ...]}}}`.

        **Errors**
        - GraphQL and network failures are surfaced via the client.

        **Example**
        ```python
        drug_api = DrugAssociationsApi()
        diseases = await drug_api.get_drug_linked_diseases(client, "CHEMBL1862")
        print([row["name"] for row in diseases["drug"]["linkedDiseases"]["rows"]])
        ```
        """
        graphql_query = """
        query DrugLinkedDiseases($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                linkedDiseases {
                    count
                    rows {
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
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})

    async def get_drug_linked_targets(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """Return targets linked to a drug via mechanism-of-action data.

        **When to use**
        - Explore which proteins a therapeutic acts upon
        - Prepare target-centric queries (e.g., fetch safety profiles for affected targets)
        - Support mechanism panels or summaries in conversational agents

        **When not to use**
        - Identifying drugs that modulate a specific target (use target association tools)
        - Investigating safety events (use drug safety APIs)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `chembl_id` (`str`): Drug identifier.

        **Returns**
        - `Dict[str, Any]`: `{"drug": {"id": str, "name": str, "linkedTargets": {"count": int, "rows": [{"id": str, "approvedSymbol": str, "approvedName": str, "biotype": str, "proteinIds": [...]}, ...]}}}`.

        **Errors**
        - Propagates GraphQL/network exceptions.

        **Example**
        ```python
        drug_api = DrugAssociationsApi()
        targets = await drug_api.get_drug_linked_targets(client, "CHEMBL1862")
        print([row["approvedSymbol"] for row in targets["drug"]["linkedTargets"]["rows"]])
        ```
        """
        graphql_query = """
        query DrugLinkedTargets($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                linkedTargets {
                    count
                    rows {
                        id
                        approvedSymbol
                        approvedName
                        biotype
                        proteinIds {
                            id
                            source
                        }
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})

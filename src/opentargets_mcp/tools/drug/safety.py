# src/opentargets_mcp/tools/drug/safety.py
"""
Defines API methods and MCP tools related to drug safety and pharmacovigilance.
"""
from typing import Any, Dict
from ...queries import OpenTargetsClient

class DrugSafetyApi:
    """
    Contains methods to query drug safety, warnings, and adverse events.
    """
    async def get_drug_adverse_events(
        self,
        client: OpenTargetsClient,
        chembl_id: str,
        page_index: int = 0,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Retrieve adverse event signals associated with a drug.

        **When to use**
        - Investigate disproportionality metrics (log-likelihood ratios) from FAERS/MedDRA
        - Provide paginated adverse event tables in agents or dashboards
        - Support pharmacovigilance reviews alongside mechanistic data

        **When not to use**
        - Checking regulatory warnings or withdrawals (use `get_drug_warnings`)
        - Exploring indication efficacy (use association tools instead)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `chembl_id` (`str`): Drug identifier.
        - `page_index` (`int`): Zero-based adverse event page (default 0).
        - `page_size` (`int`): Number of events per page (default 10).

        **Returns**
        - `Dict[str, Any]`: `{"drug": {"id": str, "name": str, "adverseEvents": {"count": int, "criticalValue": float, "rows": [{"meddraCode": str, "name": str, "count": int, "logLR": float}, ...]}}}`.

        **Errors**
        - Propagates GraphQL/network exceptions.

        **Example**
        ```python
        safety_api = DrugSafetyApi()
        adverse = await safety_api.get_drug_adverse_events(client, "CHEMBL1862", page_size=5)
        print(adverse["drug"]["adverseEvents"]["rows"][0]["name"])
        ```
        """
        graphql_query = """
        query DrugAdverseEvents($chemblId: String!, $pageIndex: Int!, $pageSize: Int!) {
            drug(chemblId: $chemblId) {
                id
                name
                adverseEvents(page: {index: $pageIndex, size: $pageSize}) {
                    count
                    criticalValue
                    rows {
                        meddraCode
                        name
                        count
                        logLR
                    }
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id, "pageIndex": page_index, "pageSize": page_size})

    async def get_drug_pharmacovigilance(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """Summarise high-level pharmacovigilance data for a drug.

        **When to use**
        - Provide a quick view that combines approval, withdrawal, black-box, and headline adverse event stats
        - Power FAQ-style responses about whether a drug carries boxed warnings or has been withdrawn

        **When not to use**
        - Inspecting detailed warning text (use `get_drug_warnings`)
        - Paging through the full adverse event catalogue (use `get_drug_adverse_events`)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `chembl_id` (`str`): Drug identifier.

        **Returns**
        - `Dict[str, Any]`: `{"drug": {"id": str, "name": str, "isApproved": bool, "hasBeenWithdrawn": bool, "blackBoxWarning": bool, "adverseEvents": {...}}}`.

        **Errors**
        - GraphQL/network exceptions bubble up from the client.

        **Example**
        ```python
        safety_api = DrugSafetyApi()
        pv = await safety_api.get_drug_pharmacovigilance(client, "CHEMBL1862")
        print(pv["drug"]["blackBoxWarning"])
        ```
        """
        graphql_query = """
        query DrugPharmacovigilance($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                isApproved
                hasBeenWithdrawn
                blackBoxWarning
                adverseEvents(page: {index: 0, size: 20}) {
                     count
                     criticalValue
                     rows {
                         meddraCode,
                         name,
                         count,
                         logLR
                     }
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})

    async def get_drug_warnings(self, client: OpenTargetsClient, chembl_id: str) -> Dict[str, Any]:
        """Fetch detailed regulatory warnings, including withdrawals and boxed labels.

        **When to use**
        - Display regulatory warning metadata (warning type, region, year, references)
        - Identify whether a drug has been withdrawn globally or in specific jurisdictions
        - Provide evidence for safety briefings or compliance workflows

        **When not to use**
        - Reviewing statistical adverse event metrics (use `get_drug_adverse_events`)
        - Checking linked diseases or targets (use association tools)

        **Parameters**
        - `client` (`OpenTargetsClient`): GraphQL client.
        - `chembl_id` (`str`): Drug identifier.

        **Returns**
        - `Dict[str, Any]`: `{"drug": {"id": str, "name": str, "hasBeenWithdrawn": bool, "blackBoxWarning": bool, "drugWarnings": [{"warningType": str, "description": str, "toxicityClass": str, "country": str, "year": int, "references": [...], ...}]}}`.

        **Errors**
        - GraphQL/network failures propagate via the client.

        **Example**
        ```python
        safety_api = DrugSafetyApi()
        warnings = await safety_api.get_drug_warnings(client, "CHEMBL1862")
        for warn in warnings["drug"]["drugWarnings"]:
            print(warn["warningType"], warn["country"])
        ```
        """
        graphql_query = """
        query DrugWarnings($chemblId: String!) {
            drug(chemblId: $chemblId) {
                id
                name
                hasBeenWithdrawn
                blackBoxWarning
                drugWarnings {
                    warningType
                    description
                    toxicityClass
                    country
                    year
                    efoId
                    efoTerm
                    efoIdForWarningClass
                    references {
                        id
                        source
                        url
                    }
                    chemblIds
                }
            }
        }
        """
        return await client._query(graphql_query, {"chemblId": chembl_id})

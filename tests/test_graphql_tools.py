# tests/test_graphql_tools.py
import pytest

from opentargets_mcp.exceptions import ValidationError
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools.graphql import GraphqlApi
from .conftest import TEST_TARGET_ID_BRAF, TEST_TARGET_ID_EGFR


@pytest.mark.asyncio
class TestGraphqlTools:
    graphql_api = GraphqlApi()

    async def test_graphql_schema(self, client: OpenTargetsClient):
        result = await self.graphql_api.graphql_schema(client)
        assert isinstance(result, str)
        assert "type Query" in result

    async def test_graphql_query(self, client: OpenTargetsClient):
        query_string = """
        query TargetInfo($ensemblId: String!) {
          target(ensemblId: $ensemblId) {
            id
            approvedSymbol
          }
        }
        """
        result = await self.graphql_api.graphql_query(
            client,
            query_string=query_string,
            variables={"ensemblId": TEST_TARGET_ID_EGFR},
        )
        assert result is not None
        assert result["status"] == "success"
        target = result["result"].get("target")
        assert target is not None
        assert target.get("approvedSymbol") == "EGFR"

    async def test_graphql_batch_query(self, client: OpenTargetsClient):
        query_string = """
        query TargetInfo($ensemblId: String!) {
          target(ensemblId: $ensemblId) {
            id
            approvedSymbol
          }
        }
        """
        result = await self.graphql_api.graphql_batch_query(
            client=client,
            query_string=query_string,
            variables_list=[
                {"ensemblId": TEST_TARGET_ID_EGFR},
                {"ensemblId": TEST_TARGET_ID_BRAF},
            ],
            key_field="ensemblId",
        )
        assert result["status"] in {"success", "warning"}
        assert result["summary"]["total"] == 2
        assert result["summary"]["failed"] == 0
        assert result["summary"]["successful"] == 2
        assert len(result["results"]) == 2
        assert {item["key"] for item in result["results"]} == {
            TEST_TARGET_ID_EGFR,
            TEST_TARGET_ID_BRAF,
        }

    async def test_graphql_query_rejects_mutation(self, client: OpenTargetsClient):
        with pytest.raises(ValidationError):
            await self.graphql_api.graphql_query(
                client,
                query_string="mutation { fakeMutation }",
            )

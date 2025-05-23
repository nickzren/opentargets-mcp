import asyncio
import json
from typing import Any, Dict, Optional
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
import mcp.types as types
from .tools import TOOLS
from .queries import OpenTargetsClient


class OpenTargetsServer:
    def __init__(self):
        self.server = Server("opentargets-mcp")
        self.client = OpenTargetsClient()
        self._setup_handlers()
    
    def _setup_handlers(self):
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            return TOOLS
        
        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> list[types.TextContent]:
            try:
                if name == "search_targets":
                    result = await self.client.search_targets(
                        arguments["query"],
                        arguments.get("size", 10)
                    )
                
                elif name == "get_target_info":
                    result = await self.client.get_target_info(
                        arguments["ensemblId"]
                    )
                
                elif name == "get_target_diseases":
                    result = await self.client.get_target_diseases(
                        arguments["ensemblId"],
                        arguments.get("page", 0),
                        arguments.get("size", 10)
                    )
                
                elif name == "get_target_drugs":
                    result = await self.client.get_target_drugs(
                        arguments["ensemblId"]
                    )
                
                elif name == "search_diseases":
                    result = await self.client.search_diseases(
                        arguments["query"],
                        arguments.get("size", 10)
                    )
                
                elif name == "get_disease_targets":
                    result = await self.client.get_disease_targets(
                        arguments["efoId"],
                        arguments.get("page", 0),
                        arguments.get("size", 10)
                    )
                
                elif name == "get_evidence":
                    result = await self.client.get_evidence(
                        arguments["ensemblId"],
                        arguments["efoId"],
                        arguments.get("datasourceIds", None),
                        arguments.get("size", 10)
                    )
                
                elif name == "get_target_safety":
                    result = await self.client.get_target_safety(
                        arguments["ensemblId"]
                    )
                
                elif name == "get_target_tractability":
                    result = await self.client.get_target_tractability(
                        arguments["ensemblId"]
                    )
                
                elif name == "get_drug_warnings":
                    result = await self.client.get_drug_warnings(
                        arguments["chemblId"]
                    )
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
                )]
    
    async def run(self):
        async with stdio_server() as (read_stream, write_stream):
            init_options = InitializationOptions(
                server_name="opentargets-mcp",
                server_version="0.1.0",
                capabilities=self.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
            await self.server.run(
                read_stream,
                write_stream,
                init_options
            )


def main():
    server = OpenTargetsServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
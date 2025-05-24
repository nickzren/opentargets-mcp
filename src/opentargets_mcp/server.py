# src/opentargets_mcp/server.py
import asyncio
import json
from typing import Any, Dict, Type
import logging
import os

# Corrected import for stdio communication and MCP models/options
from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.stdio import stdio_server 
import mcp.types as types

from .queries import OpenTargetsClient
from .tools import ALL_TOOLS, API_CLASS_MAP

# Configure basic logging for the server
log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
numeric_log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=numeric_log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OpenTargetsMcpServer:
    """
    MCP Server for Open Targets data.
    Manages the OpenTargetsClient and dispatches tool calls to appropriate API handlers.
    """
    def __init__(self):
        self.server_name = "opentargets-mcp"
        self.server_version = "0.2.4" # Incremented version for this change
        self.mcp_server = Server(self.server_name, self.server_version)
        self.client = OpenTargetsClient() 
        self._api_instances: Dict[Type, Any] = {}
        self._setup_handlers()
        logger.info(f"{self.server_name} v{self.server_version} initialized.")

    def _setup_handlers(self):
        """Registers MCP handlers for listing and calling tools."""

        @self.mcp_server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """Returns the list of all available tools."""
            return ALL_TOOLS

        @self.mcp_server.call_tool()
        async def handle_call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> list[types.TextContent]:
            """
            Handles a tool call request from an MCP client.
            """
            logger.info(f"Handling call_tool request for tool: '{name}' with arguments: {arguments}")
            try:
                if name not in API_CLASS_MAP:
                    logger.error(f"Unknown tool called: {name}")
                    raise ValueError(f"Unknown tool: {name}")

                api_class = API_CLASS_MAP[name]

                if api_class not in self._api_instances:
                    self._api_instances[api_class] = api_class()
                
                api_instance = self._api_instances[api_class]

                if not hasattr(api_instance, name):
                    logger.error(f"Tool method '{name}' not found in API class '{api_class.__name__}'")
                    raise ValueError(f"Tool method '{name}' not found in API class '{api_class.__name__}'")
                
                func_to_call = getattr(api_instance, name)

                result_data = await func_to_call(self.client, **arguments)
                
                result_json = json.dumps(result_data, indent=2)
                
                return [types.TextContent(type="text", text=result_json)]

            except Exception as e:
                logger.error(f"Error calling tool '{name}': {str(e)}", exc_info=True)
                error_response = {
                    "error": type(e).__name__,
                    "message": str(e),
                    "tool_name": name
                }
                return [types.TextContent(type="text", text=json.dumps(error_response, indent=2))]
        
        # Removed @self.mcp_server.on_shutdown() decorator and handle_shutdown method
        # as 'on_shutdown' is not an attribute of the Server object in the user's mcp library version.
        # Client cleanup will be handled by the finally block in main().

    async def run(self):
        """Starts the MCP server and listens for requests using stdio."""
        logger.info(f"Starting {self.server_name} v{self.server_version}...")
        
        init_options = InitializationOptions(
            server_name=self.server_name,             # Added server_name
            server_version=self.server_version,       # Added server_version
            capabilities=self.mcp_server.get_capabilities(
                notification_options=NotificationOptions(), 
                experimental_capabilities={}
            )
        )
        # Use the stdio_server context manager for handling read/write streams
        async with stdio_server() as (read_stream, write_stream):
            await self.mcp_server.run(read_stream, write_stream, init_options)


def main():
    """Main entry point to run the Open Targets MCP Server."""
    server = OpenTargetsMcpServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user. Shutting down.")
    except Exception as e: # Catch other potential exceptions during server run
        logger.error(f"Server encountered an unhandled exception: {e}", exc_info=True)
    finally:
        # This block ensures the client is closed if the server stops for any reason.
        logger.info("Performing final cleanup...")
        if server.client and server.client.session and not server.client.session.closed:
             logger.info("Closing OpenTargetsClient session in main's finally block.")
             try:
                 # Try to get the current running loop if available
                 loop = asyncio.get_event_loop_policy().get_event_loop()
                 if loop.is_running() and not loop.is_closed():
                     # If a loop is running and not closed, schedule close on it
                     asyncio.ensure_future(server.client.close(), loop=loop)
                 else:
                     # If no loop is running or it's closed, run a new one for cleanup
                     asyncio.run(server.client.close())
             except RuntimeError: 
                 # Fallback if get_event_loop() fails or other asyncio issues
                 logger.warning("Could not get running loop for client cleanup, attempting direct asyncio.run.")
                 asyncio.run(server.client.close())
             logger.info("OpenTargetsClient session cleanup attempted.")
        else:
            logger.info("OpenTargetsClient session was already closed or not initialized.")
        logger.info("Server shutdown complete.")


if __name__ == "__main__":
    main()

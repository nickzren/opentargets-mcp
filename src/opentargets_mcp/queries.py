# src/opentargets_mcp/queries.py
import aiohttp
import asyncio
from typing import Any, Dict, List, Optional
import time
import logging

# Configure basic logging for the client
logger = logging.getLogger(__name__)
# Set a default logging level if not configured elsewhere
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class OpenTargetsClient:
    """
    An asynchronous client for interacting with the Open Targets Platform GraphQL API.
    Includes caching functionality to reduce redundant API calls.
    """
    def __init__(self, base_url: str = "https://api.platform.opentargets.org/api/v4/graphql", cache_ttl: int = 3600):
        """
        Initializes the OpenTargetsClient.

        Args:
            base_url (str): The base URL for the Open Targets GraphQL API.
            cache_ttl (int): Time-to-live for cache entries in seconds (default is 1 hour).
        """
        self.base_url = base_url
        self.session = None
        self._cache = {}
        self._cache_ttl = cache_ttl

    async def _ensure_session(self):
        """Ensures an active aiohttp.ClientSession is available."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def _query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a GraphQL query against the Open Targets API.
        """
        await self._ensure_session()

        cache_key = f"{query}:{str(sorted(variables.items())) if variables else ''}"

        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return cached_data
            else:
                del self._cache[cache_key]

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response_text_for_error = "" # Variable to store response text in case of error

        try:
            async with self.session.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                response_text_for_error = await response.text() # Read text early for logging

                if not response.ok:
                    logger.error(
                        f"HTTP Error {response.status} for {response.url}. "
                        f"Query: {query[:200]}... Variables: {variables}. "
                        f"Response Body: {response_text_for_error}"
                    )
                    response.raise_for_status() # This will now raise ClientResponseError

                result = await response.json() # If .ok, this should succeed. If not .ok, raise_for_status handled it.
                                             # However, response.json() might fail if body was not valid JSON even on 200.

                if "errors" in result and result["errors"]:
                    logger.error(
                        f"GraphQL API errors: {result['errors']}. "
                        f"Query: {query[:200]}... Variables: {variables}."
                    )
                    # Depending on strictness, you might want to raise an exception here.
                    # For now, we return data if present, which might be partial.
                    # raise Exception(f"GraphQL API errors: {result['errors']}")

                data = result.get("data", {})
                self._cache[cache_key] = (data, time.time())
                return data

        except aiohttp.ClientResponseError as e: # Handles errors from response.raise_for_status()
            # The response_text_for_error should have been populated above if not response.ok
            # If it was an ok response but .json() failed, this specific exception might not have the body easily.
            logger.error(
                f"ClientResponseError during GraphQL query: {e}. "
                f"URL: {e.request_info.url if e.request_info else 'N/A'}, Status: {e.status}. "
                f"Query: {query[:200]}... Variables: {variables}. "
                f"Response Body (if captured): {response_text_for_error}",
                exc_info=True
            )
            raise Exception(f"HTTP request failed: {e.status}, {e.message}. Response: {response_text_for_error}") from e

        except Exception as e: # Catch-all for other unexpected errors (e.g., JSONDecodeError if response.ok but not JSON)
            logger.error(
                f"An unexpected error occurred during GraphQL query: {e}. "
                f"Query: {query[:200]}... Variables: {variables}. "
                f"Response Body (if captured): {response_text_for_error}",
                exc_info=True
            )
            raise

    async def close(self):
        """Closes the aiohttp.ClientSession."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

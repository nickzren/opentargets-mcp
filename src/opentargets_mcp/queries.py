# src/opentargets_mcp/queries.py
import aiohttp
import asyncio
from typing import Any, Dict, Optional
import time
import logging

from .exceptions import NetworkError
from .utils import generate_cache_key

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
    def __init__(
        self,
        base_url: str = "https://api.platform.opentargets.org/api/v4/graphql",
        cache_ttl: int = 3600,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initializes the OpenTargetsClient.

        Args:
            base_url (str): The base URL for the Open Targets GraphQL API.
            cache_ttl (int): Time-to-live for cache entries in seconds (default is 1 hour).
            max_retries (int): Maximum number of retry attempts for failed requests (default is 3).
            retry_delay (float): Initial delay between retries in seconds (default is 1.0).
        """
        self.base_url = base_url
        self.session = None
        self._cache = {}
        self._cache_ttl = cache_ttl
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    async def _ensure_session(self):
        """Ensures an active aiohttp.ClientSession is available."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def _query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a GraphQL query against the Open Targets API with retry logic.
        """
        await self._ensure_session()

        cache_key = generate_cache_key(query, variables)

        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return cached_data
            else:
                del self._cache[cache_key]

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        # Retry logic with exponential backoff
        last_exception = None
        for attempt in range(self._max_retries):
            response_text_for_error = ""
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
                        logger.warning(
                            f"GraphQL API returned errors: {result['errors']}. "
                            f"Query: {query[:200]}... Variables: {variables}. "
                            f"Returning partial data if available."
                        )
                        # Don't raise - return partial data if present
                        # Some queries legitimately return errors with usable data
                        # (e.g., querying non-existent IDs returns {target: None} + error)

                    data = result.get("data", {})
                    self._cache[cache_key] = (data, time.time())
                    return data

            except (aiohttp.ClientResponseError, aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                is_retryable = isinstance(e, (aiohttp.ClientError, asyncio.TimeoutError))

                if isinstance(e, aiohttp.ClientResponseError):
                    # Only retry on 5xx errors or specific 429 (rate limit)
                    is_retryable = e.status >= 500 or e.status == 429

                if is_retryable and attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self._max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(
                        f"Request failed after {attempt + 1} attempt(s): {e}. "
                        f"Query: {query[:200]}... Variables: {variables}",
                        exc_info=True
                    )
                    raise NetworkError(f"HTTP request failed: {e}") from e

            except Exception as e:
                logger.error(
                    f"Unexpected error during GraphQL query: {e}. "
                    f"Query: {query[:200]}... Variables: {variables}",
                    exc_info=True
                )
                raise

        # If we exhausted all retries
        if last_exception:
            raise NetworkError(f"Request failed after {self._max_retries} retries") from last_exception

    async def close(self):
        """Closes the aiohttp.ClientSession."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

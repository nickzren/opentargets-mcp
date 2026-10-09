# src/opentargets_mcp/queries.py
import aiohttp
import asyncio
import copy
import json
from collections import OrderedDict
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, Optional
from urllib.parse import urlsplit
from urllib.request import getproxies_environment, proxy_bypass_environment
import time
import logging

from yarl import URL

from . import __version__
from .exceptions import NetworkError, UpstreamQueryError
from .utils import generate_cache_key

# Configure basic logging for the client
logger = logging.getLogger(__name__)
# Set a default logging level if not configured elsewhere
if not logger.hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


_MAX_ERROR_MESSAGES = 5
_MAX_ERROR_MESSAGE_CHARS = 500
# A retry must leave at least this much of the request budget for its attempt.
_MIN_ATTEMPT_SECONDS = 5.0


def _env_proxy(url: str) -> tuple[URL | None, dict[str, str] | None]:
    """Return the proxy and its auth headers for ``url`` from *_PROXY/NO_PROXY only.

    Unlike aiohttp's ``trust_env``, this never reads ~/.netrc or OS proxy
    settings. Proxy credentials move into a ``Proxy-Authorization`` header so
    error text and logs never show them.
    """
    proxies = getproxies_environment()
    parts = urlsplit(url)
    proxy = proxies.get(parts.scheme)
    try:
        port = parts.port
    except ValueError:  # aiohttp reports a malformed URL when the request is made
        port = None
    # With the port included, NO_PROXY entries match as host or host:port.
    host = f"{parts.hostname}:{port}" if port else parts.hostname or ""
    if not proxy or proxy_bypass_environment(host, proxies):
        return None, None
    if "://" not in proxy:
        proxy = f"http://{proxy}"
    try:
        proxy_url = URL(proxy)
        auth = aiohttp.BasicAuth.from_url(proxy_url)
        bare_url = proxy_url.with_user(None)
    except ValueError:
        # The value may hold credentials, so it is not echoed.
        raise NetworkError("Invalid proxy URL in the environment") from None
    headers = {"Proxy-Authorization": auth.encode()} if auth else None
    return bare_url, headers


def _retry_after_seconds(response: Any) -> int:
    """Return a Retry-After delta-seconds value; an HTTP-date counts as 0."""
    headers = getattr(response, "headers", None) or {}
    try:
        return min(int(headers.get("Retry-After", "")), 86400)
    except ValueError:
        return 0


def _extract_graphql_errors(payload: Any) -> list[str]:
    """Return sanitized ``errors[].message`` strings from a GraphQL envelope."""
    if not isinstance(payload, dict):
        return []
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return []
    messages: list[str] = []
    for entry in errors[:_MAX_ERROR_MESSAGES]:
        if not isinstance(entry, dict):
            continue
        message = entry.get("message")
        if isinstance(message, str) and message.strip():
            messages.append(" ".join(message.split())[:_MAX_ERROR_MESSAGE_CHARS])
    return messages


@dataclass(frozen=True)
class _GraphQLHTTPResult:
    ok: bool
    status: int
    url: str
    text: str
    payload: Dict[str, Any] | None
    error: aiohttp.ClientResponseError | None = None


class OpenTargetsClient:
    """
    An asynchronous client for interacting with the Open Targets Platform GraphQL API.
    Includes caching functionality to reduce redundant API calls.
    """

    def __init__(
        self,
        base_url: str = "https://api.platform.opentargets.org/api/v4/graphql",
        cache_ttl: int = 3600,
        cache_max_entries: int = 2048,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        request_budget: float = 60.0,
    ):
        """
        Initializes the OpenTargetsClient.

        Args:
            base_url (str): The base URL for the Open Targets GraphQL API.
            cache_ttl (int): Time-to-live for cache entries in seconds (default is 1 hour).
            cache_max_entries (int): Maximum number of cache entries to keep in memory.
            max_retries (int): Maximum number of retry attempts for failed requests (default is 3).
            retry_delay (float): Initial delay between retries in seconds (default is 1.0).
            request_budget (float): Total seconds per request, across all attempts and retry delays (default is 60.0).
        """
        if cache_ttl < 0:
            raise ValueError("cache_ttl must be >= 0")
        if cache_max_entries < 1:
            raise ValueError("cache_max_entries must be >= 1")
        if max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        if retry_delay < 0:
            raise ValueError("retry_delay must be >= 0")
        if not 0 < request_budget < float("inf"):
            raise ValueError("request_budget must be a positive finite number")

        self.base_url = base_url
        self.session: aiohttp.ClientSession | None = None
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._cache_ttl = cache_ttl
        self._cache_max_entries = cache_max_entries
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._request_budget = request_budget

    async def _ensure_session(self):
        """Ensures an active aiohttp.ClientSession is available."""
        if self.session is None or self.session.closed:
            # trust_env would also send ~/.netrc credentials; see _env_proxy.
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": f"opentargets-mcp/{__version__}"},
                trust_env=False,
            )

    def _get_cached(self, cache_key: str) -> Any | None:
        if self._cache_ttl == 0:
            return None

        cached_entry = self._cache.get(cache_key)
        if cached_entry is None:
            return None

        cached_data, timestamp = cached_entry
        if time.time() - timestamp >= self._cache_ttl:
            del self._cache[cache_key]
            return None

        self._cache.move_to_end(cache_key)
        return copy.deepcopy(cached_data)

    def _set_cached(self, cache_key: str, data: Any) -> None:
        if self._cache_ttl == 0:
            return

        self._cache[cache_key] = (copy.deepcopy(data), time.time())
        self._cache.move_to_end(cache_key)

        while len(self._cache) > self._cache_max_entries:
            self._cache.popitem(last=False)

    @staticmethod
    def _try_parse_json_response(response_text: str) -> Dict[str, Any] | None:
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        return payload

    @classmethod
    def _parse_json_response(cls, response_text: str) -> Dict[str, Any]:
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise NetworkError(
                "Received non-JSON response from Open Targets API"
            ) from exc

        if not isinstance(payload, dict):
            raise NetworkError(
                "Received unexpected JSON response shape from Open Targets API"
            )

        return payload

    async def _post_graphql(
        self,
        payload: Dict[str, Any],
        *,
        query_for_log: str,
        variables_for_log: Optional[Dict[str, Any]] = None,
    ) -> _GraphQLHTTPResult:
        await self._ensure_session()
        proxy, proxy_headers = _env_proxy(self.base_url)
        headers = {"Content-Type": "application/json"}
        follow_redirects = True
        if proxy_headers and urlsplit(self.base_url).scheme != "https":
            # Without a CONNECT tunnel the request itself goes to the proxy.
            # Its credentials then ride in the request headers, which a
            # redirect would carry to the next host, so redirects are refused.
            headers.update(proxy_headers)
            proxy_headers = None
            follow_redirects = False
        deadline = time.monotonic() + self._request_budget
        last_exception = None

        for attempt in range(self._max_retries):
            remaining = deadline - time.monotonic()
            if not remaining > 0:
                # aiohttp treats a non-positive timeout as no timeout at all.
                raise NetworkError(
                    f"Request budget of {self._request_budget:g} s exhausted "
                    f"after {attempt} attempt(s)"
                ) from last_exception
            try:
                assert self.session is not None
                async with self.session.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    proxy=proxy,
                    proxy_headers=proxy_headers,
                    allow_redirects=follow_redirects,
                    timeout=aiohttp.ClientTimeout(total=remaining),
                ) as response:
                    if not follow_redirects and 300 <= response.status < 400:
                        raise NetworkError(
                            f"HTTP {response.status} redirect refused: requests through "
                            "an authenticated HTTP proxy do not follow redirects; "
                            "point the API URL at the final address"
                        )
                    response_text = await response.text()
                    result = _GraphQLHTTPResult(
                        ok=response.ok,
                        status=response.status,
                        url=str(response.url),
                        text=response_text,
                        payload=self._try_parse_json_response(response_text),
                        error=None
                        if response.ok
                        else aiohttp.ClientResponseError(
                            request_info=getattr(response, "request_info", None)
                            or SimpleNamespace(real_url=str(response.url)),
                            history=getattr(response, "history", ()),
                            status=response.status,
                            message=getattr(response, "reason", response_text),
                            headers=getattr(response, "headers", None),
                        ),
                    )

                    if result.ok:
                        return result

                    logger.error(
                        "HTTP Error %s for %s. Query: %s... Variables: %s. "
                        "Response Body: %s",
                        result.status,
                        result.url,
                        query_for_log[:200],
                        variables_for_log,
                        result.text,
                    )

                    delay = self._retry_delay * (2**attempt)
                    if result.status in (429, 503):
                        delay = max(delay, _retry_after_seconds(response))
                    if (
                        (result.status >= 500 or result.status == 429)
                        and attempt < self._max_retries - 1
                        and deadline - time.monotonic() > delay + _MIN_ATTEMPT_SECONDS
                    ):
                        logger.warning(
                            "Request failed (attempt %s/%s): HTTP %s. "
                            "Retrying in %.1fs...",
                            attempt + 1,
                            self._max_retries,
                            result.status,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    logger.error(
                        "Request failed after %s attempt(s): HTTP %s. "
                        "Query: %s... Variables: %s",
                        attempt + 1,
                        result.status,
                        query_for_log[:200],
                        variables_for_log,
                    )
                    return result

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ) as exc:
                last_exception = exc
                delay = self._retry_delay * (2**attempt)
                if (
                    attempt < self._max_retries - 1
                    and deadline - time.monotonic() > delay + _MIN_ATTEMPT_SECONDS
                ):
                    logger.warning(
                        "Request failed (attempt %s/%s): %s. Retrying in %.1fs...",
                        attempt + 1,
                        self._max_retries,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error(
                    "Request failed after %s attempt(s): %s. Query: %s... "
                    "Variables: %s",
                    attempt + 1,
                    exc,
                    query_for_log[:200],
                    variables_for_log,
                    exc_info=True,
                )
                # str(asyncio.TimeoutError()) is empty; name the type instead.
                raise NetworkError(
                    f"HTTP request failed: {str(exc) or type(exc).__name__}"
                ) from exc

            except NetworkError:
                raise
            except Exception as exc:
                logger.error(
                    "Unexpected error during GraphQL query: %s. Query: %s... "
                    "Variables: %s",
                    exc,
                    query_for_log[:200],
                    variables_for_log,
                    exc_info=True,
                )
                raise

        if last_exception:
            raise NetworkError(
                f"Request failed after {self._max_retries} retries"
            ) from last_exception

        raise NetworkError("Request failed without making any attempts")

    async def _query(
        self, query: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes a GraphQL query against the Open Targets API with retry logic.
        """
        cache_key = generate_cache_key(query, variables)

        cached_data = self._get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = await self._post_graphql(
            payload,
            query_for_log=query,
            variables_for_log=variables,
        )
        if not response.ok:
            upstream_errors = _extract_graphql_errors(response.payload)
            error = response.error or aiohttp.ClientResponseError(
                request_info=SimpleNamespace(real_url=response.url),
                history=(),
                status=response.status,
                message=response.text,
                headers=None,
            )
            if upstream_errors:
                raise UpstreamQueryError(
                    upstream_errors, status=response.status
                ) from error
            raise NetworkError(f"HTTP request failed: {error}") from error

        result = self._parse_json_response(response.text)

        if "errors" in result and result["errors"]:
            logger.warning(
                "GraphQL API returned errors: %s. Query: %s... Variables: %s.",
                result["errors"],
                query[:200],
                variables,
            )
            raise UpstreamQueryError(
                _extract_graphql_errors(result) or ["Upstream GraphQL error"],
                status=response.status,
            )

        data = result.get("data", {})
        self._set_cached(cache_key, data)
        return copy.deepcopy(data)

    async def close(self):
        """Closes the aiohttp.ClientSession."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

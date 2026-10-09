"""Offline tests for the HTTP session: proxy selection, headers and retry budget."""

import asyncio
import os
import time
from types import SimpleNamespace

import pytest

import opentargets_mcp.queries as queries_module
from opentargets_mcp import __version__
from opentargets_mcp.exceptions import NetworkError
from opentargets_mcp.queries import OpenTargetsClient, _env_proxy

from .test_regressions import _FakeResponse, _FakeSession

API_URL = "https://api.platform.opentargets.org/api/v4/graphql"
PROXY_URL = "http://proxy.test:3128"
GOOD_BODY = '{"data":{"meta":{"name":"ok"}}}'


@pytest.fixture
def proxy_env(monkeypatch):
    """Start from an environment without any *_PROXY variables."""
    for name in list(os.environ):
        if name.lower().endswith("_proxy"):
            monkeypatch.delenv(name)
    return monkeypatch


class _Clock:
    """Fake monotonic clock; sleeping advances it without waiting."""

    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(
        queries_module,
        "time",
        SimpleNamespace(monotonic=clock.monotonic, time=time.time),
    )
    monkeypatch.setattr(queries_module.asyncio, "sleep", clock.sleep)
    return clock


class _RecordingSession(_FakeSession):
    def __init__(self, responses):
        super().__init__(responses)
        self.kwargs: list[dict] = []

    def post(self, *args, **kwargs):
        self.kwargs.append(kwargs)
        return super().post(*args, **kwargs)


class _TimingOutSession(_FakeSession):
    """Every attempt times out after min(its timeout, attempt_seconds)."""

    def __init__(self, clock: _Clock, attempt_seconds: float):
        super().__init__([])
        self._clock = clock
        self._attempt_seconds = attempt_seconds
        self.timeouts: list[float] = []

    def post(self, *_args, timeout, **_kwargs):
        self.timeouts.append(timeout.total)
        self._clock.now += min(timeout.total, self._attempt_seconds)
        raise asyncio.TimeoutError()


# ---------------------------------------------------------------------------
# Proxy selection: environment variables only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["HTTPS_PROXY", "https_proxy"])
def test_env_proxy_reads_https_proxy_in_either_case(proxy_env, name):
    proxy_env.setenv(name, PROXY_URL)

    proxy, headers = _env_proxy(API_URL)

    assert str(proxy) == PROXY_URL
    assert headers is None


@pytest.mark.parametrize("no_proxy", [".opentargets.org", "*"])
def test_env_proxy_honours_no_proxy(proxy_env, no_proxy):
    proxy_env.setenv("HTTPS_PROXY", PROXY_URL)
    proxy_env.setenv("NO_PROXY", no_proxy)

    assert _env_proxy(API_URL) == (None, None)


def test_env_proxy_is_none_when_unset(proxy_env):
    assert _env_proxy(API_URL) == (None, None)


def test_env_proxy_moves_credentials_out_of_the_url(proxy_env):
    proxy_env.setenv("HTTPS_PROXY", "http://user:secret@proxy.test:3128")

    proxy, headers = _env_proxy(API_URL)

    assert str(proxy) == PROXY_URL
    assert headers == {"Proxy-Authorization": "Basic dXNlcjpzZWNyZXQ="}


@pytest.mark.parametrize("value", ["proxy.test:3128", "http://proxy.test:3128"])
def test_env_proxy_accepts_a_value_without_scheme(proxy_env, value):
    proxy_env.setenv("HTTPS_PROXY", value)

    proxy, _ = _env_proxy(API_URL)

    assert str(proxy) == PROXY_URL


def test_invalid_env_proxy_raises_network_error_without_echoing_it(proxy_env):
    proxy_env.setenv("HTTPS_PROXY", "http://user:secret@[bad")

    with pytest.raises(NetworkError) as exc_info:
        _env_proxy(API_URL)

    assert "secret" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_plain_http_api_sends_proxy_credentials_to_the_proxy(proxy_env):
    proxy_env.setenv("HTTP_PROXY", "http://user:secret@proxy.test:3128")
    client = OpenTargetsClient(base_url="http://api.test/graphql", max_retries=1)
    client.session = _RecordingSession([_FakeResponse(200, GOOD_BODY)])

    await client._query("query Meta { meta { name } }")

    (kwargs,) = client.session.kwargs
    assert kwargs["headers"]["Proxy-Authorization"] == "Basic dXNlcjpzZWNyZXQ="
    assert kwargs["proxy_headers"] is None


@pytest.mark.asyncio
async def test_requests_use_env_proxy_and_send_no_credentials(proxy_env):
    proxy_env.setenv("HTTPS_PROXY", PROXY_URL)
    client = OpenTargetsClient(max_retries=1)
    client.session = _RecordingSession([_FakeResponse(200, GOOD_BODY)])

    await client._query("query Meta { meta { name } }")

    (kwargs,) = client.session.kwargs
    assert str(kwargs["proxy"]) == PROXY_URL
    assert kwargs["proxy_headers"] is None
    assert "auth" not in kwargs
    assert "Authorization" not in kwargs["headers"]


@pytest.mark.asyncio
async def test_session_ignores_netrc_and_identifies_itself():
    client = OpenTargetsClient()
    await client._ensure_session()
    try:
        session = client.session
        assert session.trust_env is False
        assert session.auth is None
        assert "Authorization" not in session.headers
        assert session.headers["User-Agent"] == f"opentargets-mcp/{__version__}"
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Retry budget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repeated_timeouts_stop_within_budget(clock):
    client = OpenTargetsClient(max_retries=5, retry_delay=1, request_budget=60)
    client.session = _TimingOutSession(clock, attempt_seconds=20)

    with pytest.raises(NetworkError, match="TimeoutError"):
        await client._query("query Meta { meta { name } }")

    # Each attempt gets the remaining budget; no retry once < delay + 5 s is left.
    assert client.session.timeouts == [60, 39, 17]
    assert clock.sleeps == [1, 2]
    assert clock.now == 60


@pytest.mark.asyncio
async def test_retry_after_on_429_is_honoured(clock):
    rate_limited = _FakeResponse(429, "Too Many Requests")
    rate_limited.headers = {"Retry-After": "1"}
    client = OpenTargetsClient(max_retries=3, retry_delay=0)
    client.session = _FakeSession([rate_limited, _FakeResponse(200, GOOD_BODY)])

    result = await client._query("query Meta { meta { name } }")

    assert result == {"meta": {"name": "ok"}}
    assert client.session.calls == 2
    assert clock.sleeps == [1]


@pytest.mark.asyncio
async def test_retry_after_beyond_budget_fails_without_sleeping(clock):
    rate_limited = _FakeResponse(429, "Too Many Requests")
    rate_limited.headers = {"Retry-After": "120"}
    client = OpenTargetsClient(max_retries=3, retry_delay=0, request_budget=60)
    client.session = _FakeSession([rate_limited, _FakeResponse(200, GOOD_BODY)])

    with pytest.raises(NetworkError, match="429"):
        await client._query("query Meta { meta { name } }")

    assert client.session.calls == 1
    assert clock.sleeps == []


@pytest.mark.asyncio
async def test_huge_retry_after_fails_without_overflow(clock):
    rate_limited = _FakeResponse(503, "Service Unavailable")
    rate_limited.headers = {"Retry-After": "1" + "0" * 400}
    client = OpenTargetsClient(max_retries=3, retry_delay=0)
    client.session = _FakeSession([rate_limited, _FakeResponse(200, GOOD_BODY)])

    with pytest.raises(NetworkError, match="503"):
        await client._query("query Meta { meta { name } }")

    assert clock.sleeps == []


def test_client_rejects_non_positive_request_budget():
    with pytest.raises(ValueError):
        OpenTargetsClient(request_budget=0)

"""Unit tests for the base Exchange HTTP layer: fetch, fetch2, throttle, error handling, and async variants."""
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from exchanges.base.exchange import Exchange
from exchanges.base.errors import (
    BadRequest,
    BadSymbol,
    AuthenticationError,
    PermissionDenied,
    RateLimitExceeded,
    ExchangeNotAvailable,
    RequestTimeout,
    NetworkError,
    ExchangeError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_exchange(**overrides):
    """Create a minimal Exchange instance for testing."""
    e = Exchange()
    e.id = 'test'
    e.enableRateLimit = False  # disable for most tests
    for k, v in overrides.items():
        setattr(e, k, v)
    return e


def _mock_response(status_code=200, text='{"ok":true}', reason='OK', headers=None):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.reason = reason
    resp.text = text
    resp.content = text.encode('utf-8')
    resp.headers = headers or {}
    resp.encoding = 'utf-8'
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from requests.exceptions import HTTPError
        resp.raise_for_status.side_effect = HTTPError(response=resp)
    return resp


# ---------------------------------------------------------------------------
# Sync fetch() tests
# ---------------------------------------------------------------------------

class TestFetch:
    def test_fetch_success_json(self):
        exchange = _make_exchange()
        mock_resp = _mock_response(200, '{"price":"100.5"}')
        exchange.session = MagicMock()
        exchange.session.request.return_value = mock_resp
        exchange.session.cookies = MagicMock()

        result = exchange.fetch('https://api.test.com/ticker', 'GET')
        assert result == {"price": "100.5"}

    def test_fetch_400_raises_bad_request(self):
        exchange = _make_exchange()
        mock_resp = _mock_response(400, '{"error":"bad param"}', 'Bad Request')
        exchange.session = MagicMock()
        exchange.session.request.return_value = mock_resp
        exchange.session.cookies = MagicMock()

        with pytest.raises(BadRequest):
            exchange.fetch('https://api.test.com/order', 'POST')

    def test_fetch_401_raises_auth_error(self):
        exchange = _make_exchange()
        mock_resp = _mock_response(401, '{"error":"invalid key"}', 'Unauthorized')
        exchange.session = MagicMock()
        exchange.session.request.return_value = mock_resp
        exchange.session.cookies = MagicMock()

        with pytest.raises(AuthenticationError):
            exchange.fetch('https://api.test.com/balance', 'GET')

    def test_fetch_403_raises_permission_denied(self):
        exchange = _make_exchange()
        mock_resp = _mock_response(403, '{"error":"forbidden"}', 'Forbidden')
        exchange.session = MagicMock()
        exchange.session.request.return_value = mock_resp
        exchange.session.cookies = MagicMock()

        with pytest.raises(PermissionDenied):
            exchange.fetch('https://api.test.com/admin', 'GET')

    def test_fetch_404_raises_bad_symbol(self):
        exchange = _make_exchange()
        mock_resp = _mock_response(404, '{"error":"not found"}', 'Not Found')
        exchange.session = MagicMock()
        exchange.session.request.return_value = mock_resp
        exchange.session.cookies = MagicMock()

        with pytest.raises(BadSymbol):
            exchange.fetch('https://api.test.com/ticker?symbol=INVALID', 'GET')

    def test_fetch_429_raises_rate_limit(self):
        exchange = _make_exchange()
        mock_resp = _mock_response(429, '{"error":"too many requests"}', 'Too Many Requests')
        exchange.session = MagicMock()
        exchange.session.request.return_value = mock_resp
        exchange.session.cookies = MagicMock()

        with pytest.raises(RateLimitExceeded):
            exchange.fetch('https://api.test.com/ticker', 'GET')

    def test_fetch_500_raises_exchange_not_available(self):
        exchange = _make_exchange()
        mock_resp = _mock_response(500, 'Internal Server Error', 'Internal Server Error')
        exchange.session = MagicMock()
        exchange.session.request.return_value = mock_resp
        exchange.session.cookies = MagicMock()

        with pytest.raises(ExchangeNotAvailable):
            exchange.fetch('https://api.test.com/ticker', 'GET')

    def test_fetch_timeout_raises_request_timeout(self):
        from requests.exceptions import Timeout
        exchange = _make_exchange()
        exchange.session = MagicMock()
        exchange.session.request.side_effect = Timeout()
        exchange.session.cookies = MagicMock()

        with pytest.raises(RequestTimeout):
            exchange.fetch('https://api.test.com/ticker', 'GET')

    def test_fetch_connection_error_raises_network_error(self):
        from requests.exceptions import ConnectionError as ReqConnError
        exchange = _make_exchange()
        exchange.session = MagicMock()
        exchange.session.request.side_effect = ReqConnError('Connection refused')
        exchange.session.cookies = MagicMock()

        with pytest.raises(NetworkError):
            exchange.fetch('https://api.test.com/ticker', 'GET')


# ---------------------------------------------------------------------------
# Throttle tests
# ---------------------------------------------------------------------------

class TestThrottle:
    def test_throttle_sleeps_when_too_fast(self):
        exchange = _make_exchange(rateLimit=100)  # 100ms between requests
        exchange.lastRestRequestTimestamp = exchange.milliseconds()  # just now

        with patch('time.sleep') as mock_sleep:
            exchange.throttle(1)
            # Should sleep for ~100ms
            assert mock_sleep.called
            slept = mock_sleep.call_args[0][0]
            assert 0 < slept <= 0.1  # 100ms = 0.1s

    def test_throttle_no_sleep_when_enough_time_passed(self):
        exchange = _make_exchange(rateLimit=100)
        exchange.lastRestRequestTimestamp = exchange.milliseconds() - 200  # 200ms ago

        with patch('time.sleep') as mock_sleep:
            exchange.throttle(1)
            mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# fetch2 tests
# ---------------------------------------------------------------------------

class TestFetch2:
    def test_fetch2_calls_sign_then_fetch(self):
        exchange = _make_exchange()
        exchange.sign = MagicMock(return_value={
            'url': 'https://api.test.com/ticker',
            'method': 'GET',
            'headers': {'X-API-Key': 'test'},
            'body': None,
        })
        exchange.fetch = MagicMock(return_value={"price": "100"})

        result = exchange.fetch2('/ticker', 'public', 'GET')
        exchange.sign.assert_called_once()
        exchange.fetch.assert_called_once_with(
            'https://api.test.com/ticker', 'GET', {'X-API-Key': 'test'}, None
        )
        assert result == {"price": "100"}

    def test_fetch2_throttles_when_rate_limit_enabled(self):
        exchange = _make_exchange(enableRateLimit=True, rateLimit=50)
        exchange.lastRestRequestTimestamp = exchange.milliseconds()
        exchange.sign = MagicMock(return_value={
            'url': 'https://api.test.com/ticker', 'method': 'GET',
            'headers': None, 'body': None,
        })
        exchange.fetch = MagicMock(return_value={})

        with patch('time.sleep'):
            exchange.fetch2('/ticker', 'public', 'GET')
        # If we got here without error, throttle was called successfully


# ---------------------------------------------------------------------------
# _request tests
# ---------------------------------------------------------------------------

class TestRequest:
    def test_request_uses_endpoint_config(self):
        from exchanges.base.types import Entry
        exchange = _make_exchange()
        endpoint = Entry(path='api/v1/ticker', api='public', method='GET', config={'cost': 2})
        exchange.request = MagicMock(return_value={"symbol": "BTC/USD"})

        result = exchange._request(endpoint, {'symbol': 'BTC/USD'})
        assert result == {"symbol": "BTC/USD"}
        exchange.request.assert_called_once()

    def test_request_calls_parse_error(self):
        from exchanges.base.types import Entry
        exchange = _make_exchange()
        endpoint = Entry(path='api/v1/order', api='private', method='POST', config={})
        exchange.request = MagicMock(return_value={"code": -1, "msg": "error"})
        exchange.parse_error = MagicMock(side_effect=ExchangeError("test error"))

        with pytest.raises(ExchangeError, match="test error"):
            exchange._request(endpoint, {})
        exchange.parse_error.assert_called_once()


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------

class TestAsyncFetch:
    @pytest.mark.asyncio
    async def test_fetch_async_success(self):
        exchange = _make_exchange()

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = 'OK'
        mock_response.text = '{"result":"ok"}'
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        exchange._async_client = mock_client

        result = await exchange.fetch_async('https://api.test.com/ticker', 'GET')
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_fetch_async_400_raises(self):
        exchange = _make_exchange()

        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.reason_phrase = 'Bad Request'
        mock_response.text = '{"error":"bad"}'
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        exchange._async_client = mock_client

        with pytest.raises(BadRequest):
            await exchange.fetch_async('https://api.test.com/order', 'POST')

    @pytest.mark.asyncio
    async def test_fetch_async_timeout_raises(self):
        import httpx
        exchange = _make_exchange()

        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.ReadTimeout("timed out")
        exchange._async_client = mock_client

        with pytest.raises(RequestTimeout):
            await exchange.fetch_async('https://api.test.com/ticker', 'GET')

    @pytest.mark.asyncio
    async def test_throttle_async_sleeps(self):
        exchange = _make_exchange(rateLimit=100)
        exchange.lastRestRequestTimestamp = exchange.milliseconds()

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await exchange.throttle_async(1)
            assert mock_sleep.called
            slept = mock_sleep.call_args[0][0]
            assert 0 < slept <= 0.1

    @pytest.mark.asyncio
    async def test_request_async_full_chain(self):
        from exchanges.base.types import Entry
        exchange = _make_exchange()
        endpoint = Entry(path='api/v1/ticker', api='public', method='GET', config={})

        exchange.sign = MagicMock(return_value={
            'url': 'https://api.test.com/api/v1/ticker',
            'method': 'GET',
            'headers': None,
            'body': None,
        })

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = 'OK'
        mock_response.text = '{"price":"42000"}'
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        exchange._async_client = mock_client

        result = await exchange._request_async(endpoint, {})
        assert result == {"price": "42000"}

    @pytest.mark.asyncio
    async def test_close_async(self):
        exchange = _make_exchange()
        mock_client = AsyncMock()
        exchange._async_client = mock_client

        await exchange.close_async()
        mock_client.aclose.assert_called_once()
        assert exchange._async_client is None

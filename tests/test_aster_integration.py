"""Test Aster exchange integration with unified architecture."""
import pytest
from decimal import Decimal

from exchanges.aster import aster
from exchanges.base.errors import (
    ExchangeError,
    InvalidOrder,
    InsufficientFunds,
    OrderNotFound,
    AuthenticationError,
    OperationFailed,
    InvalidNonce,
    ArgumentsRequired,
)


class TestAsterClient:
    """Test Aster REST API client."""

    @pytest.fixture
    def client(self):
        """Create Aster client without credentials."""
        return aster({})

    def test_client_initialization(self, client):
        """Test client initializes with correct settings."""
        assert client.id == "aster"
        assert client.has["fetchTicker"]
        assert client.has["createOrder"]
        assert client.has["fetchBalance"]

    def test_describe_method(self, client):
        """Test describe method returns correct metadata."""
        desc = client.describe()
        assert desc["id"] == "aster"
        assert desc["name"] == "Aster Futures"
        assert "api" in desc["urls"]

    def test_parse_error_invalid_order(self, client):
        """Test parse_error handles invalid order errors."""
        response = {"code": -1102, "msg": "Mandatory parameter 'timeInForce' was not sent"}

        with pytest.raises(ArgumentsRequired):
            client.parse_error(response)

    def test_parse_error_insufficient_funds(self, client):
        """Test parse_error handles insufficient funds errors."""
        response = {"code": -2019, "msg": "Margin is insufficient"}

        with pytest.raises(InsufficientFunds):
            client.parse_error(response)

    def test_parse_error_order_not_found(self, client):
        """Test parse_error handles order not found errors."""
        response = {"code": -2011, "msg": "Unknown order sent"}

        with pytest.raises(OrderNotFound):
            client.parse_error(response)

    def test_parse_error_authentication(self, client):
        """Test parse_error handles authentication errors."""
        response = {"code": -1022, "msg": "Signature verification failed"}

        with pytest.raises(AuthenticationError):
            client.parse_error(response)

    def test_parse_error_no_error(self, client):
        """Test parse_error does nothing for valid responses."""
        response = {"symbol": "XAUUSDT", "price": "4596.50"}

        # Should not raise
        client.parse_error(response)

    def test_parse_error_none_response(self, client):
        """Test parse_error handles None response."""
        # Should not raise
        client.parse_error(None)


class TestAsterErrorMapping:
    """Test comprehensive error code mapping."""

    @pytest.fixture
    def client(self):
        return aster({})

    @pytest.mark.parametrize("error_code,error_msg,expected_exception", [
        ("-1000", "Unknown error", OperationFailed),
        ("-1021", "Timestamp out of recv window", InvalidNonce),
        ("-1102", "Missing parameter", ArgumentsRequired),
        ("-2010", "Account insufficient balance", InvalidOrder),
        ("-2011", "Unknown order", OrderNotFound),
        ("-1022", "Invalid signature", AuthenticationError),
    ])
    def test_error_code_mapping(self, client, error_code, error_msg, expected_exception):
        """Test that error codes map to correct exception types."""
        response = {"code": int(error_code), "msg": error_msg}

        with pytest.raises(expected_exception):
            client.parse_error(response)


class TestAsterEndpoints:
    """Test Aster endpoint configuration."""

    @pytest.fixture
    def client(self):
        return aster({})

    def test_endpoints_exist(self, client):
        """Test that endpoints are properly configured."""
        assert hasattr(client, "endpoints")
        assert client.endpoints is not None

    def test_has_required_endpoints(self, client):
        """Test that required API endpoints are defined."""
        # Check public endpoints
        assert hasattr(client.endpoints, "public_get_fapi_v1_exchangeinfo")
        assert hasattr(client.endpoints, "public_get_fapi_v1_ticker_price")
        assert hasattr(client.endpoints, "public_get_fapi_v1_depth")

        # Check private endpoints
        assert hasattr(client.endpoints, "private_post_fapi_v1_order")
        assert hasattr(client.endpoints, "private_get_fapi_v2_balance")
        assert hasattr(client.endpoints, "private_delete_fapi_v1_order")


@pytest.mark.skip(reason="Requires live API credentials")
class TestAsterLiveAPI:
    """Live API tests (requires credentials)."""

    @pytest.fixture
    def client(self):
        """Create authenticated Aster client."""
        # In real tests, load from environment
        return aster({
            "apiKey": "your_api_key",
            "secret": "your_secret"
        })

    async def test_fetch_ticker(self, client):
        """Test fetching ticker data."""
        ticker = await client.fetch_ticker("XAU/USDT")
        assert "bid" in ticker
        assert "ask" in ticker
        assert ticker["symbol"] == "XAU/USDT"

    async def test_create_limit_order(self, client):
        """Test creating limit order."""
        order = await client.create_order(
            symbol="XAU/USDT",
            order_type="limit",
            side="buy",
            amount=Decimal("0.001"),
            price=Decimal("4500.0")
        )
        assert order["id"] is not None
        assert order["status"] in ["open", "NEW"]

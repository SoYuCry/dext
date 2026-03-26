"""Tests for precision handling and HTTP error mapping in base exchange."""
import pytest
from exchanges.base.decimal_to_precision import (
    decimal_to_precision,
    TRUNCATE,
    ROUND,
    DECIMAL_PLACES,
    TICK_SIZE,
    NO_PADDING,
    PAD_WITH_ZERO,
)
from exchanges.base.errors import (
    BadRequest,
    BadSymbol,
    AuthenticationError,
    PermissionDenied,
    RateLimitExceeded,
    ExchangeNotAvailable,
    RequestTimeout,
    ExchangeError,
    InvalidOrder,
)


# ---------------------------------------------------------------------------
# decimal_to_precision TICK_SIZE mode
# ---------------------------------------------------------------------------

class TestTickSizePrecision:
    """Test TICK_SIZE mode with actual tick values (not integer decimal places)."""

    def test_tick_size_basic_truncate(self):
        # stepSize=0.001, amount=0.002 should stay 0.002
        assert decimal_to_precision(0.002, TRUNCATE, 0.001, TICK_SIZE) == '0.002'

    def test_tick_size_basic_round(self):
        assert decimal_to_precision(0.0025, ROUND, 0.001, TICK_SIZE) == '0.003'
        assert decimal_to_precision(0.0024, ROUND, 0.001, TICK_SIZE) == '0.002'

    def test_tick_size_truncate_removes_excess(self):
        # 0.00259 truncated to stepSize=0.001 → 0.002
        assert decimal_to_precision(0.00259, TRUNCATE, 0.001, TICK_SIZE) == '0.002'

    def test_tick_size_exact_multiple(self):
        assert decimal_to_precision(0.003, TRUNCATE, 0.001, TICK_SIZE) == '0.003'
        assert decimal_to_precision(0.003, ROUND, 0.001, TICK_SIZE) == '0.003'

    def test_tick_size_larger_values(self):
        # stepSize=0.01, amount=1.234 → truncate to 1.23
        assert decimal_to_precision(1.234, TRUNCATE, 0.01, TICK_SIZE) == '1.23'
        # round to 1.23
        assert decimal_to_precision(1.234, ROUND, 0.01, TICK_SIZE) == '1.23'
        # round to 1.24
        assert decimal_to_precision(1.235, ROUND, 0.01, TICK_SIZE) == '1.24'

    def test_tick_size_with_padding(self):
        assert decimal_to_precision(1.2, ROUND, 0.01, TICK_SIZE, PAD_WITH_ZERO) == '1.20'

    def test_tick_size_integer_step(self):
        # stepSize=5, amount=12 → truncate to 10
        assert decimal_to_precision(12, TRUNCATE, 5, TICK_SIZE) == '10'
        # round to 10
        assert decimal_to_precision(12, ROUND, 5, TICK_SIZE) == '10'
        # round to 15
        assert decimal_to_precision(13, ROUND, 5, TICK_SIZE) == '15'

    def test_tick_size_zero_raises(self):
        with pytest.raises(AssertionError, match='negative or zero'):
            decimal_to_precision(1.0, TRUNCATE, 0, TICK_SIZE)

    def test_tick_size_small_amount_not_zero(self):
        """The bug case: stepSize=0.001, amount=0.002 must NOT become '0'."""
        result = decimal_to_precision(0.002, TRUNCATE, 0.001, TICK_SIZE)
        assert result != '0', f"Bug: 0.002 with stepSize=0.001 became '0'"
        assert result == '0.002'

    def test_tick_size_very_small(self):
        # stepSize=0.00001, amount=0.000023 → truncate to 0.00002
        assert decimal_to_precision(0.000023, TRUNCATE, 0.00001, TICK_SIZE) == '0.00002'


# ---------------------------------------------------------------------------
# amount_to_precision with TICK_SIZE mode and integer precision values
# ---------------------------------------------------------------------------

class TestAmountToPrecisionIntegerFix:
    """Test the fix for integer precision values in TICK_SIZE mode.

    When precisionMode=TICK_SIZE but precision['amount'] is stored as an integer
    (decimal places count, e.g. 3) instead of tick size (e.g. 0.001), the base
    class should auto-convert.
    """

    def _make_exchange(self, precision_amount, precision_mode=TICK_SIZE):
        """Create a minimal exchange-like object for testing."""
        from exchanges.base.exchange import Exchange
        exchange = Exchange()
        exchange.id = 'test'
        exchange.precisionMode = precision_mode
        exchange.paddingMode = NO_PADDING
        exchange.markets = {
            'TEST/USDT': {
                'symbol': 'TEST/USDT',
                'precision': {
                    'amount': precision_amount,
                    'price': 2,
                },
            }
        }
        exchange.markets_by_id = {}
        return exchange

    def test_integer_precision_converted_to_tick_size(self):
        """precision=3 in TICK_SIZE mode should behave like stepSize=0.001"""
        exchange = self._make_exchange(3)
        result = exchange.amount_to_precision('TEST/USDT', 0.002)
        assert result == '0.002'

    def test_integer_precision_8_decimals(self):
        """precision=8 (like Binance baseAssetPrecision) should work."""
        exchange = self._make_exchange(8)
        result = exchange.amount_to_precision('TEST/USDT', 0.12345678)
        assert result == '0.12345678'

    def test_float_tick_size_unchanged(self):
        """precision=0.01 (already a tick size) should work as before."""
        exchange = self._make_exchange(0.01)
        result = exchange.amount_to_precision('TEST/USDT', 1.234)
        assert result == '1.23'

    def test_zero_amount_raises(self):
        """amount=0.0001 with precision=3 (stepSize=0.001) truncates to 0, should raise."""
        exchange = self._make_exchange(3)
        with pytest.raises(InvalidOrder):
            exchange.amount_to_precision('TEST/USDT', 0.0001)

    def test_price_to_precision_integer_fix(self):
        """price_to_precision should also handle integer precision in TICK_SIZE mode."""
        exchange = self._make_exchange(3)
        # price precision is 2 → should behave like tickSize=0.01
        result = exchange.price_to_precision('TEST/USDT', 123.456)
        assert result == '123.46'


# ---------------------------------------------------------------------------
# HTTP exception mapping
# ---------------------------------------------------------------------------

class TestHttpExceptionMapping:
    """Verify httpExceptions maps status codes to correct exception types."""

    def _get_http_exceptions(self):
        from exchanges.base.exchange import Exchange
        return Exchange.httpExceptions

    def test_400_is_bad_request(self):
        exceptions = self._get_http_exceptions()
        assert exceptions['400'] is BadRequest

    def test_401_is_authentication_error(self):
        exceptions = self._get_http_exceptions()
        assert exceptions['401'] is AuthenticationError

    def test_403_is_permission_denied(self):
        exceptions = self._get_http_exceptions()
        assert exceptions['403'] is PermissionDenied

    def test_404_is_bad_symbol(self):
        exceptions = self._get_http_exceptions()
        assert exceptions['404'] is BadSymbol

    def test_429_is_rate_limit(self):
        exceptions = self._get_http_exceptions()
        assert exceptions['429'] is RateLimitExceeded

    def test_5xx_is_exchange_not_available(self):
        exceptions = self._get_http_exceptions()
        for code in ['500', '501', '502', '503']:
            assert exceptions[code] is ExchangeNotAvailable, f"{code} should be ExchangeNotAvailable"

    def test_408_504_is_request_timeout(self):
        exceptions = self._get_http_exceptions()
        assert exceptions['408'] is RequestTimeout
        assert exceptions['504'] is RequestTimeout

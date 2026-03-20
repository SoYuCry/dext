# -*- coding: utf-8 -*-
"""
Tests that each exchange's ``has`` capability dict matches the methods
actually implemented on the class.

Rules
-----
* If ``has[key]`` is ``True`` (or a truthy string like ``"emulated"``),
  the corresponding snake_case method must exist and must not be a bare
  stub that only raises ``NotSupported``.  The method may live on the
  subclass itself **or** be a base-class convenience wrapper (e.g.
  ``create_limit_order`` delegates to ``create_order``).
* If ``has[key]`` is ``False``, the method must **not** be overridden
  by the exchange subclass.
* Keys that are not method capabilities (``spot``, ``margin``, etc.)
  are skipped.

No network calls are made -- we only inspect class hierarchies and source.
"""

import importlib
import inspect
import re
import pytest
import dext
from exchanges.base.exchange import Exchange

# ── helpers ──────────────────────────────────────────────────────────────

# Capability keys that do NOT map to a method
_NON_METHOD_KEYS = frozenset({
    "CORS",
    "publicAPI",
    "privateAPI",
    "sandbox",
    "spot",
    "margin",
    "swap",
    "future",
    "option",
})


def _camel_to_snake(name: str) -> str:
    """Convert camelCase capability name to snake_case method name.

    ``fetchOrderBook`` -> ``fetch_order_book``
    ``fetchOHLCV``     -> ``fetch_ohlcv``
    """
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    return s.lower()


def _is_overridden(cls, method_name: str) -> bool:
    """Return True if *cls* defines *method_name* itself (not just inherits)."""
    for klass in cls.__mro__:
        if method_name in klass.__dict__:
            return klass is not Exchange
    return False


def _is_not_supported_stub(cls, method_name: str) -> bool:
    """Return True if the method is a base-class stub that only raises NotSupported.

    These stubs have a body consisting solely of:
        raise NotSupported(...)
    """
    method = getattr(cls, method_name, None)
    if method is None:
        return True
    try:
        source = inspect.getsource(method)
    except (OSError, TypeError):
        return False
    # Strip the def line and docstring, look for the pattern
    lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip()
        and not line.strip().startswith("def ")
        and not line.strip().startswith('"""')
        and not line.strip().startswith("'''")
        and not line.strip().startswith("#")
        and not line.strip().startswith("@")
    ]
    # A stub has exactly one meaningful line: raise NotSupported(...)
    if len(lines) == 1 and lines[0].startswith("raise NotSupported("):
        return True
    return False


# ── exchange classes under test ──────────────────────────────────────────

_EXCHANGE_MODULES = {
    "aster": ("exchanges.aster", "aster"),
    "backpack": ("exchanges.backpack", "backpack"),
    "binance": ("exchanges.binance", "binance"),
    "lighter": ("exchanges.lighter", "lighter"),
}


def _load_class(name: str):
    mod_path, attr = _EXCHANGE_MODULES[name]
    mod = importlib.import_module(mod_path)
    return getattr(mod, attr)


def _get_has_dict(cls):
    """Instantiate with no credentials and return the ``has`` dict."""
    instance = cls()
    return instance.has


# ── parametrised capability tests ────────────────────────────────────────

def _collect_cases():
    """Yield (exchange_name, capability_key, expected_value) tuples."""
    for name in _EXCHANGE_MODULES:
        cls = _load_class(name)
        has = _get_has_dict(cls)
        for key, value in has.items():
            if key in _NON_METHOD_KEYS:
                continue
            yield name, key, value


_CASES = list(_collect_cases())

@pytest.mark.parametrize(
    "exchange_name,capability,expected",
    [c for c in _CASES if c[2] is True or (isinstance(c[2], str) and c[2])],
    ids=lambda val: val if isinstance(val, str) else None,
)
def test_true_capability_has_working_method(exchange_name, capability, expected):
    """If ``has[capability]`` is truthy the method must exist and not be a
    bare NotSupported stub."""
    cls = _load_class(exchange_name)
    method_name = _camel_to_snake(capability)

    assert hasattr(cls, method_name), (
        f"{exchange_name}.has['{capability}'] is {expected!r} but "
        f"method '{method_name}' does not exist on the class"
    )

    # The method must NOT be a bare NotSupported stub.
    # It should either be overridden by the subclass or be a base-class
    # convenience wrapper that delegates to another method.
    assert not _is_not_supported_stub(cls, method_name), (
        f"{exchange_name}.has['{capability}'] is {expected!r} but "
        f"'{method_name}' is just a NotSupported stub -- either implement "
        f"the method or set the capability to False"
    )


@pytest.mark.parametrize(
    "exchange_name,capability,expected",
    [c for c in _CASES if c[2] is False],
    ids=lambda val: val if isinstance(val, str) else None,
)
def test_false_capability_not_overridden(exchange_name, capability, expected):
    """If ``has[capability]`` is False the method must NOT be overridden."""
    cls = _load_class(exchange_name)
    method_name = _camel_to_snake(capability)

    assert not _is_overridden(cls, method_name), (
        f"{exchange_name}.has['{capability}'] is False but "
        f"'{method_name}' IS overridden -- either remove the override "
        f"or set the capability to True"
    )


# ── public API surface tests ────────────────────────────────────────────

class TestPublicAPISurface:
    """Verify the top-level ``dext`` package exposes exchanges correctly."""

    @pytest.mark.parametrize("name", ["aster", "backpack", "binance", "lighter"])
    def test_exchange_in_exchanges_list(self, name):
        assert name in dext.exchanges

    @pytest.mark.parametrize("name", ["aster", "backpack", "binance", "lighter"])
    def test_dext_getattr_returns_class(self, name):
        cls = getattr(dext, name)
        assert isinstance(cls, type) and issubclass(cls, Exchange)

    @pytest.mark.parametrize("name", ["aster", "backpack", "binance", "lighter"])
    def test_get_client_returns_instance(self, name):
        client = dext.get_client(name)
        assert isinstance(client, Exchange)

    def test_variational_in_exchanges_list(self):
        """Variational is listed but uses a custom class."""
        assert "variational" in dext.exchanges


# ── has property access tests ─────────────────────────────────────────────

class TestHasPropertyAccess:
    """Verify that exchange.has provides convenient capability checking."""

    def test_has_property_access(self):
        from exchanges.lighter import lighter
        ex = lighter()
        assert ex.has['fetchTicker'] is True

    def test_has_returns_dict(self):
        from exchanges.lighter import lighter
        ex = lighter()
        assert isinstance(ex.has, dict)

    def test_has_false_capability(self):
        from exchanges.lighter import lighter
        ex = lighter()
        assert ex.has['spot'] is False

    def test_has_none_capability(self):
        from exchanges.lighter import lighter
        ex = lighter()
        assert ex.has['CORS'] is None

    @pytest.mark.parametrize("exchange_name", list(_EXCHANGE_MODULES.keys()))
    def test_has_available_on_all_exchanges(self, exchange_name):
        cls = _load_class(exchange_name)
        ex = cls()
        assert isinstance(ex.has, dict)
        assert len(ex.has) > 0


class TestCamelToSnake:
    @pytest.mark.parametrize("camel,expected", [
        ("fetchTicker", "fetch_ticker"),
        ("fetchOrderBook", "fetch_order_book"),
        ("createOrder", "create_order"),
        ("fetchOHLCV", "fetch_ohlcv"),
        ("cancelAllOrders", "cancel_all_orders"),
        ("fetchMyTrades", "fetch_my_trades"),
        ("createMarketBuyOrderWithCost", "create_market_buy_order_with_cost"),
        ("setLeverage", "set_leverage"),
        ("addMargin", "add_margin"),
        ("fetchFundingRateHistory", "fetch_funding_rate_history"),
        ("fetchOpenInterestHistory", "fetch_open_interest_history"),
        ("createOrders", "create_orders"),
        ("withdraw", "withdraw"),
        ("transfer", "transfer"),
        ("fetchL2OrderBook", "fetch_l2_order_book"),
    ])
    def test_conversion(self, camel, expected):
        assert _camel_to_snake(camel) == expected

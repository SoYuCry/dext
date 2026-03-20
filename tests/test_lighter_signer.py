from exchanges.lighter_signer import SimpleSignerClient


def _make_client(monkeypatch):
    """Create a SimpleSignerClient with native library calls stubbed out."""
    monkeypatch.setattr(SimpleSignerClient, "_load_library", lambda self, d: None)
    monkeypatch.setattr(SimpleSignerClient, "_configure_library", lambda self: None)
    monkeypatch.setattr(SimpleSignerClient, "_create_client", lambda self: None)
    return SimpleSignerClient(
        base_url="https://example.invalid",
        private_key="1" * 64,
        account_index=0,
        api_key_index=0,
    )


def test_place_market_order_uses_ioc_limit_and_valid_expiry(monkeypatch):
    client = _make_client(monkeypatch)

    monkeypatch.setattr(client, "fetch_market_multipliers", lambda _market_index: (10**3, 10**3))

    captured = {}

    def fake_create_order(**kwargs):
        captured.update(kwargs)
        return {"client_order_index": kwargs["client_order_index"]}, {"tx_hash": "0x0"}, None

    monkeypatch.setattr(client, "create_order", fake_create_order)

    order = client.place_market_order(market_index=0, side="sell", amount=0.05, price=3336.99)
    assert order
    assert captured["time_in_force"] == client.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL
    assert captured["order_type"] == client.ORDER_TYPE_LIMIT
    assert captured["order_expiry"] == client.DEFAULT_IOC_EXPIRY


def test_place_market_order_uses_payload_market_index(monkeypatch):
    client = _make_client(monkeypatch)
    monkeypatch.setattr(client, "fetch_market_multipliers", lambda _market_index: (10**3, 10**3))

    def fake_create_order(**kwargs):
        return {"ClientOrderIndex": kwargs["client_order_index"], "MarketIndex": 7}, {"tx_hash": "0x0"}, None

    monkeypatch.setattr(client, "create_order", fake_create_order)
    order = client.place_market_order(market_index=999, side="buy", amount=0.01, price=1.23)
    assert order["order_id"] == str(order["raw"]["payload"]["ClientOrderIndex"])


def test_place_market_order_sets_order_id_from_uppercase(monkeypatch):
    client = _make_client(monkeypatch)
    monkeypatch.setattr(client, "fetch_market_multipliers", lambda _market_index: (10**3, 10**3))

    def fake_create_order(**kwargs):
        return {"ClientOrderIndex": kwargs["client_order_index"]}, {"tx_hash": "0x0"}, None

    monkeypatch.setattr(client, "create_order", fake_create_order)

    order = client.place_market_order(market_index=0, side="buy", amount=0.05, price=200.0)
    assert order["order_id"] == str(order["raw"]["payload"]["ClientOrderIndex"])


def test_fetch_market_multipliers_supports_spot(monkeypatch):
    client = _make_client(monkeypatch)

    class DummyResponse:
        def json(self):
            return {
                "spot_order_book_details": [
                    {"market_id": 2048, "supported_size_decimals": 4, "supported_price_decimals": 2}
                ]
            }

    class DummySession:
        def get(self, *args, **kwargs):
            return DummyResponse()

    client.session = DummySession()

    multipliers = client.fetch_market_multipliers(2048)
    assert multipliers == (10 ** 4, 10 ** 2)
    assert client._market_multipliers[2048] == multipliers

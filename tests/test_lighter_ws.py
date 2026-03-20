from exchanges.ws.lighter import LighterWS


def test_derive_fill_prefers_quote_base_ratio():
    ws = LighterWS(market_index=0, on_event=lambda _: None)
    order = {
        "price": "3350.00",
        "filled_base_amount": "0.0050",
        "filled_quote_amount": "16.666850",
    }
    derived = ws._derive_fill_fields(order)
    assert derived["filled_amount"] == 0.005
    # 16.666850 / 0.0050 = 3333.37
    assert abs(derived["fill_price"] - 3333.37) < 1e-6


def test_derive_fill_requires_base_and_quote():
    ws = LighterWS(market_index=0, on_event=lambda _: None)
    order = {"filled_base_amount": "0.0050"}
    derived = ws._derive_fill_fields(order)
    assert derived == {}

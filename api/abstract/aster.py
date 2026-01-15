from ..base.types import Entry


class ImplicitAPI:
    # Public API - fapi endpoints
    public_get_fapi_v1_ping = publicGetFapiV1Ping = Entry('fapi/v1/ping', 'public', 'GET', {'cost': 1})
    public_get_fapi_v1_time = publicGetFapiV1Time = Entry('fapi/v1/time', 'public', 'GET', {'cost': 1})
    public_get_fapi_v1_exchangeinfo = publicGetFapiV1ExchangeInfo = Entry('fapi/v1/exchangeInfo', 'public', 'GET', {'cost': 1})
    public_get_fapi_v1_depth = publicGetFapiV1Depth = Entry('fapi/v1/depth', 'public', 'GET', {'cost': 1})
    public_get_fapi_v1_trades = publicGetFapiV1Trades = Entry('fapi/v1/trades', 'public', 'GET', {'cost': 1})
    public_get_fapi_v1_klines = publicGetFapiV1Klines = Entry('fapi/v1/klines', 'public', 'GET', {'cost': 1})
    public_get_fapi_v1_ticker_24hr = publicGetFapiV1Ticker24hr = Entry('fapi/v1/ticker/24hr', 'public', 'GET', {'cost': 1})
    public_get_fapi_v1_ticker_price = publicGetFapiV1TickerPrice = Entry('fapi/v1/ticker/price', 'public', 'GET', {'cost': 1})
    public_get_fapi_v1_premiumindex = publicGetFapiV1PremiumIndex = Entry('fapi/v1/premiumIndex', 'public', 'GET', {'cost': 1})
    public_get_fapi_v1_fundingrate = publicGetFapiV1FundingRate = Entry('fapi/v1/fundingRate', 'public', 'GET', {'cost': 1})

    # Private API - fapi endpoints
    private_get_fapi_v1_order = privateGetFapiV1Order = Entry('fapi/v1/order', 'private', 'GET', {'cost': 1})
    private_get_fapi_v1_openorders = privateGetFapiV1OpenOrders = Entry('fapi/v1/openOrders', 'private', 'GET', {'cost': 1})
    private_get_fapi_v1_allorders = privateGetFapiV1AllOrders = Entry('fapi/v1/allOrders', 'private', 'GET', {'cost': 1})
    private_get_fapi_v2_balance = privateGetFapiV2Balance = Entry('fapi/v2/balance', 'private', 'GET', {'cost': 1})
    private_get_fapi_v2_positionrisk = privateGetFapiV2PositionRisk = Entry('fapi/v2/positionRisk', 'private', 'GET', {'cost': 1})
    private_get_fapi_v1_usertrades = privateGetFapiV1UserTrades = Entry('fapi/v1/userTrades', 'private', 'GET', {'cost': 1})

    private_post_fapi_v1_order = privatePostFapiV1Order = Entry('fapi/v1/order', 'private', 'POST', {'cost': 1})

    private_delete_fapi_v1_order = privateDeleteFapiV1Order = Entry('fapi/v1/order', 'private', 'DELETE', {'cost': 1})
    private_delete_fapi_v1_allopenorders = privateDeleteFapiV1AllOpenOrders = Entry('fapi/v1/allOpenOrders', 'private', 'DELETE', {'cost': 1})

    # Public API - sapi endpoints
    public_get_sapi_v1_ping = publicGetSapiV1Ping = Entry('sapi/v1/ping', 'public', 'GET', {'cost': 1})
    public_get_sapi_v1_time = publicGetSapiV1Time = Entry('sapi/v1/time', 'public', 'GET', {'cost': 1})
    public_get_sapi_v1_exchangeinfo = publicGetSapiV1ExchangeInfo = Entry('sapi/v1/exchangeInfo', 'public', 'GET', {'cost': 1})

    # Private API - sapi endpoints
    private_get_sapi_v1_account = privateGetSapiV1Account = Entry('sapi/v1/account', 'private', 'GET', {'cost': 1})
    private_post_sapi_v1_order = privatePostSapiV1Order = Entry('sapi/v1/order', 'private', 'POST', {'cost': 1})
    private_delete_sapi_v1_order = privateDeleteSapiV1Order = Entry('sapi/v1/order', 'private', 'DELETE', {'cost': 1})

from ..base.types import Entry


class AsterEndpoints:
    def __init__(self):
        # Public API - fapi endpoints
        self.public_get_fapi_v1_ping = self.publicGetFapiV1Ping = Entry('fapi/v1/ping', 'public', 'GET', {'cost': 1})
        self.public_get_fapi_v1_time = self.publicGetFapiV1Time = Entry('fapi/v1/time', 'public', 'GET', {'cost': 1})
        self.public_get_fapi_v1_exchangeinfo = self.publicGetFapiV1ExchangeInfo = Entry('fapi/v1/exchangeInfo', 'public', 'GET', {'cost': 1})
        self.public_get_fapi_v1_depth = self.publicGetFapiV1Depth = Entry('fapi/v1/depth', 'public', 'GET', {'cost': 1})
        self.public_get_fapi_v1_trades = self.publicGetFapiV1Trades = Entry('fapi/v1/trades', 'public', 'GET', {'cost': 1})
        self.public_get_fapi_v1_klines = self.publicGetFapiV1Klines = Entry('fapi/v1/klines', 'public', 'GET', {'cost': 1})
        self.public_get_fapi_v1_ticker_24hr = self.publicGetFapiV1Ticker24hr = Entry('fapi/v1/ticker/24hr', 'public', 'GET', {'cost': 1})
        self.public_get_fapi_v1_ticker_price = self.publicGetFapiV1TickerPrice = Entry('fapi/v1/ticker/price', 'public', 'GET', {'cost': 1})
        self.public_get_fapi_v1_premiumindex = self.publicGetFapiV1PremiumIndex = Entry('fapi/v1/premiumIndex', 'public', 'GET', {'cost': 1})
        self.public_get_fapi_v1_fundingrate = self.publicGetFapiV1FundingRate = Entry('fapi/v1/fundingRate', 'public', 'GET', {'cost': 1})

        # Private API - fapi endpoints
        self.private_get_fapi_v1_order = self.privateGetFapiV1Order = Entry('fapi/v1/order', 'private', 'GET', {'cost': 1})
        self.private_get_fapi_v1_openorders = self.privateGetFapiV1OpenOrders = Entry('fapi/v1/openOrders', 'private', 'GET', {'cost': 1})
        self.private_get_fapi_v1_allorders = self.privateGetFapiV1AllOrders = Entry('fapi/v1/allOrders', 'private', 'GET', {'cost': 1})
        self.private_get_fapi_v2_balance = self.privateGetFapiV2Balance = Entry('fapi/v2/balance', 'private', 'GET', {'cost': 1})
        self.private_get_fapi_v2_positionrisk = self.privateGetFapiV2PositionRisk = Entry('fapi/v2/positionRisk', 'private', 'GET', {'cost': 1})
        self.private_get_fapi_v1_usertrades = self.privateGetFapiV1UserTrades = Entry('fapi/v1/userTrades', 'private', 'GET', {'cost': 1})

        self.private_post_fapi_v1_order = self.privatePostFapiV1Order = Entry('fapi/v1/order', 'private', 'POST', {'cost': 1})
        self.private_post_fapi_v1_leverage = self.privatePostFapiV1Leverage = Entry('fapi/v1/leverage', 'private', 'POST', {'cost': 1})

        self.private_delete_fapi_v1_order = self.privateDeleteFapiV1Order = Entry('fapi/v1/order', 'private', 'DELETE', {'cost': 1})
        self.private_delete_fapi_v1_allopenorders = self.privateDeleteFapiV1AllOpenOrders = Entry('fapi/v1/allOpenOrders', 'private', 'DELETE', {'cost': 1})

        # Public API - sapi endpoints
        self.public_get_sapi_v1_ping = self.publicGetSapiV1Ping = Entry('sapi/v1/ping', 'public', 'GET', {'cost': 1})
        self.public_get_sapi_v1_time = self.publicGetSapiV1Time = Entry('sapi/v1/time', 'public', 'GET', {'cost': 1})
        self.public_get_sapi_v1_exchangeinfo = self.publicGetSapiV1ExchangeInfo = Entry('sapi/v1/exchangeInfo', 'public', 'GET', {'cost': 1})

        # Private API - sapi endpoints
        self.private_get_sapi_v1_account = self.privateGetSapiV1Account = Entry('sapi/v1/account', 'private', 'GET', {'cost': 1})
        self.private_post_sapi_v1_order = self.privatePostSapiV1Order = Entry('sapi/v1/order', 'private', 'POST', {'cost': 1})
        self.private_delete_sapi_v1_order = self.privateDeleteSapiV1Order = Entry('sapi/v1/order', 'private', 'DELETE', {'cost': 1})

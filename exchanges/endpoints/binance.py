from ..base.types import Entry


class BinanceEndpoints:
    """Binance Spot API endpoints.

    API Documentation: https://binance-docs.github.io/apidocs/spot/en/
    Base URL: https://api.binance.com
    """

    def __init__(self):
        # Public endpoints - Market Data
        self.public_get_api_v3_ping = self.publicGetApiV3Ping = Entry('api/v3/ping', 'public', 'GET', {'cost': 1})
        self.public_get_api_v3_time = self.publicGetApiV3Time = Entry('api/v3/time', 'public', 'GET', {'cost': 1})
        self.public_get_api_v3_exchangeinfo = self.publicGetApiV3ExchangeInfo = Entry('api/v3/exchangeInfo', 'public', 'GET', {'cost': 10})
        self.public_get_api_v3_depth = self.publicGetApiV3Depth = Entry('api/v3/depth', 'public', 'GET', {'cost': 1})
        self.public_get_api_v3_trades = self.publicGetApiV3Trades = Entry('api/v3/trades', 'public', 'GET', {'cost': 1})
        self.public_get_api_v3_historicaltrades = self.publicGetApiV3HistoricalTrades = Entry('api/v3/historicalTrades', 'public', 'GET', {'cost': 5})
        self.public_get_api_v3_aggtrades = self.publicGetApiV3AggTrades = Entry('api/v3/aggTrades', 'public', 'GET', {'cost': 1})
        self.public_get_api_v3_klines = self.publicGetApiV3Klines = Entry('api/v3/klines', 'public', 'GET', {'cost': 1})
        self.public_get_api_v3_uiklines = self.publicGetApiV3UiKlines = Entry('api/v3/uiKlines', 'public', 'GET', {'cost': 1})
        self.public_get_api_v3_avgprice = self.publicGetApiV3AvgPrice = Entry('api/v3/avgPrice', 'public', 'GET', {'cost': 1})
        self.public_get_api_v3_ticker_24hr = self.publicGetApiV3Ticker24hr = Entry('api/v3/ticker/24hr', 'public', 'GET', {'cost': 1})
        self.public_get_api_v3_ticker_price = self.publicGetApiV3TickerPrice = Entry('api/v3/ticker/price', 'public', 'GET', {'cost': 1})
        self.public_get_api_v3_ticker_bookticker = self.publicGetApiV3TickerBookTicker = Entry('api/v3/ticker/bookTicker', 'public', 'GET', {'cost': 1})
        self.public_get_api_v3_ticker = self.publicGetApiV3Ticker = Entry('api/v3/ticker', 'public', 'GET', {'cost': 2})

        # Private endpoints - Account
        self.private_get_api_v3_account = self.privateGetApiV3Account = Entry('api/v3/account', 'private', 'GET', {'cost': 10})
        self.private_get_api_v3_myTrades = self.privateGetApiV3MyTrades = Entry('api/v3/myTrades', 'private', 'GET', {'cost': 10})
        self.private_get_api_v3_ratelimit_order = self.privateGetApiV3RateLimitOrder = Entry('api/v3/rateLimit/order', 'private', 'GET', {'cost': 20})

        # Private endpoints - Trading
        self.private_post_api_v3_order_test = self.privatePostApiV3OrderTest = Entry('api/v3/order/test', 'private', 'POST', {'cost': 1})
        self.private_post_api_v3_order = self.privatePostApiV3Order = Entry('api/v3/order', 'private', 'POST', {'cost': 1})
        self.private_delete_api_v3_order = self.privateDeleteApiV3Order = Entry('api/v3/order', 'private', 'DELETE', {'cost': 1})
        self.private_delete_api_v3_openorders = self.privateDeleteApiV3OpenOrders = Entry('api/v3/openOrders', 'private', 'DELETE', {'cost': 1})
        self.private_get_api_v3_order = self.privateGetApiV3Order = Entry('api/v3/order', 'private', 'GET', {'cost': 2})
        self.private_get_api_v3_openorders = self.privateGetApiV3OpenOrders = Entry('api/v3/openOrders', 'private', 'GET', {'cost': 3})
        self.private_get_api_v3_allorders = self.privateGetApiV3AllOrders = Entry('api/v3/allOrders', 'private', 'GET', {'cost': 10})

        # Private endpoints - OCO Orders
        self.private_post_api_v3_order_oco = self.privatePostApiV3OrderOco = Entry('api/v3/order/oco', 'private', 'POST', {'cost': 1})
        self.private_delete_api_v3_orderlist = self.privateDeleteApiV3OrderList = Entry('api/v3/orderList', 'private', 'DELETE', {'cost': 1})
        self.private_get_api_v3_orderlist = self.privateGetApiV3OrderList = Entry('api/v3/orderList', 'private', 'GET', {'cost': 2})
        self.private_get_api_v3_allorderlist = self.privateGetApiV3AllOrderList = Entry('api/v3/allOrderList', 'private', 'GET', {'cost': 10})
        self.private_get_api_v3_openorderlist = self.privateGetApiV3OpenOrderList = Entry('api/v3/openOrderList', 'private', 'GET', {'cost': 3})

        # User Data Stream
        self.private_post_api_v3_userdatastream = self.privatePostApiV3UserDataStream = Entry('api/v3/userDataStream', 'private', 'POST', {'cost': 1})
        self.private_put_api_v3_userdatastream = self.privatePutApiV3UserDataStream = Entry('api/v3/userDataStream', 'private', 'PUT', {'cost': 1})
        self.private_delete_api_v3_userdatastream = self.privateDeleteApiV3UserDataStream = Entry('api/v3/userDataStream', 'private', 'DELETE', {'cost': 1})

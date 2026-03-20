from ..base.types import Entry


class LighterEndpoints:
    def __init__(self):
        # Public API endpoints
        self.public_get_status = self.publicGetStatus = Entry('api/v1/status', 'public', 'GET', {'cost': 1})
        self.public_get_orderbooks = self.publicGetOrderbooks = Entry('api/v1/orderBookDetails', 'public', 'GET', {'cost': 1})
        self.public_get_orderbooks_market_id = self.publicGetOrderbooksMarketId = Entry('api/v1/orderBookOrders', 'public', 'GET', {'cost': 1})
        self.public_get_orderbooks_market_id_details = self.publicGetOrderbooksMarketIdDetails = Entry('api/v1/orderBookDetails', 'public', 'GET', {'cost': 1})
        self.public_get_markets = self.publicGetMarkets = Entry('api/v1/orderBookDetails', 'public', 'GET', {'cost': 1})
        self.public_get_markets_market_id = self.publicGetMarketsMarketId = Entry('api/v1/orderBookDetails', 'public', 'GET', {'cost': 1})
        self.public_get_trades = self.publicGetTrades = Entry('api/v1/trades', 'public', 'GET', {'cost': 1})
        self.public_get_trades_market_id = self.publicGetTradesMarketId = Entry('api/v1/trades', 'public', 'GET', {'cost': 1})
        self.public_get_candles = self.publicGetCandles = Entry('api/v1/candlesticks', 'public', 'GET', {'cost': 1})
        self.public_get_funding_rates = self.publicGetFundingRates = Entry('api/v1/funding-rates', 'public', 'GET', {'cost': 1})

        # Private API endpoints
        self.private_get_accounts = self.privateGetAccounts = Entry('api/v1/account', 'private', 'GET', {'cost': 1})
        self.private_get_accounts_account_index = self.privateGetAccountsAccountIndex = Entry('api/v1/account', 'private', 'GET', {'cost': 1})
        self.private_get_orders = self.privateGetOrders = Entry('api/v1/accountActiveOrders', 'private', 'GET', {'cost': 1})
        self.private_get_orders_active = self.privateGetOrdersActive = Entry('api/v1/accountActiveOrders', 'private', 'GET', {'cost': 1})
        self.private_get_orders_history = self.privateGetOrdersHistory = Entry('api/v1/orders/history', 'private', 'GET', {'cost': 1})
        self.private_get_fills = self.privateGetFills = Entry('api/v1/trades', 'private', 'GET', {'cost': 1})
        self.private_get_positions = self.privateGetPositions = Entry('api/v1/account', 'private', 'GET', {'cost': 1})

        self.private_post_orders = self.privatePostOrders = Entry('api/v1/orders', 'private', 'POST', {'cost': 1})
        self.private_post_orders_cancel = self.privatePostOrdersCancel = Entry('api/v1/orders/cancel', 'private', 'POST', {'cost': 1})
        self.private_post_orders_cancel_all = self.privatePostOrdersCancelAll = Entry('api/v1/orders/cancel-all', 'private', 'POST', {'cost': 1})

from ..base.types import Entry


class VariationalEndpoints:
    def __init__(self):
        # Public endpoints
        self.public_get_instruments = self.publicGetInstruments = Entry('instruments', 'public', 'GET', {})
        self.public_get_status = self.publicGetStatus = Entry('status', 'public', 'GET', {})

        # Private endpoints (require authentication via Cookie + vr-connected-address)
        self.private_post_quotes_indicative = self.privatePostQuotesIndicative = Entry('quotes/indicative', 'private', 'POST', {})
        self.private_post_orders_new_market = self.privatePostOrdersNewMarket = Entry('orders/new/market', 'private', 'POST', {})
        self.private_post_orders_new_limit = self.privatePostOrdersNewLimit = Entry('orders/new/limit', 'private', 'POST', {})
        self.private_post_orders_cancel = self.privatePostOrdersCancel = Entry('orders/cancel', 'private', 'POST', {})
        self.private_get_orders_v2 = self.privateGetOrdersV2 = Entry('orders/v2', 'private', 'GET', {})
        self.private_get_positions = self.privateGetPositions = Entry('positions', 'private', 'GET', {})
        self.private_get_transfers = self.privateGetTransfers = Entry('transfers', 'private', 'GET', {})

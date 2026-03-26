"""Exchange wrappers used by the strategy."""
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from exchanges import get_client
from logger import setup_logger

logger = setup_logger("xau.exchanges")


@dataclass
class OrderRef:
    order_id: str
    symbol: str
    side: str
    price: float
    amount: float
    info: Dict[str, Any]


class ExchangeWrapper:
    """Thin wrapper around ccxt-style client to keep strategy code concise.

    Uses the async REST interface (_request_async) when available, falling
    back to asyncio.to_thread() for methods not yet ported to async.
    """

    def __init__(self, name: str, config: Dict[str, Any]) -> None:
        self.name = name
        self.client = get_client(name, config)
        self.symbol = config.get("symbol")

    async def _call(self, method, *args, **kwargs):
        """Call a sync exchange method via asyncio.to_thread (fallback helper)."""
        return await asyncio.to_thread(method, *args, **kwargs)

    async def create_limit_order(self, symbol: str, side: str, amount: float, price: float) -> Optional[OrderRef]:
        return await self._create_order(symbol, side, amount, price, "limit")

    async def create_market_order(self, symbol: str, side: str, amount: float) -> Optional[OrderRef]:
        return await self._create_order(symbol, side, amount, None, "market")

    async def _create_order(self, symbol: str, side: str, amount: float, price: Optional[float], otype: str) -> Optional[OrderRef]:
        try:
            if price is not None:
                order = await self._call(self.client.create_order, symbol, otype, side, amount, price)
            else:
                order = await self._call(self.client.create_order, symbol, otype, side, amount)
            return OrderRef(
                order_id=str(order.get("id")),
                symbol=symbol,
                side=side,
                price=float(order.get("price") or price or 0),
                amount=float(order.get("amount") or amount),
                info=order,
            )
        except Exception as exc:
            logger.error(f"[{self.name}] create_order failed: {exc}")
            return None

    async def cancel_orders(self, symbol: str, order_ids: List[str]) -> None:
        async def _cancel(oid):
            try:
                await self._call(self.client.cancel_order, oid, symbol)
            except Exception as exc:
                logger.warning(f"[{self.name}] cancel_order {oid} failed: {exc}")
        await asyncio.gather(*(_cancel(oid) for oid in order_ids))

    async def fetch_order(self, symbol: str, order_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._call(self.client.fetch_order, order_id, symbol)
        except Exception as exc:
            logger.warning(f"[{self.name}] fetch_order {order_id} failed: {exc}")
            return None

    async def fetch_open_orders(self, symbol: str) -> List[Dict[str, Any]]:
        try:
            orders = await self._call(self.client.fetch_open_orders, symbol)
            return orders or []
        except Exception as exc:
            logger.warning(f"[{self.name}] fetch_open_orders failed: {exc}")
            return []

    async def fetch_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._call(self.client.fetch_ticker, symbol)
        except Exception as exc:
            logger.warning(f"[{self.name}] fetch_ticker failed: {exc}")
            return None

    async def has_symbol(self, symbol: str) -> bool:
        """Check whether the exchange lists the symbol (by symbol or id)."""
        try:
            markets = await self._call(self.client.fetch_markets)
        except Exception as exc:
            logger.warning(f"[{self.name}] fetch_markets failed: {exc}")
            return False
        symbol_u = (symbol or "").upper()
        for m in markets or []:
            if (m.get("symbol") or "").upper() == symbol_u:
                return True
            if (m.get("id") or "").upper() == symbol_u:
                return True
        return False

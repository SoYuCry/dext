"""Lighter WebSocket client.

Features:
- Order book snapshot + incremental updates
- Optional account orders stream
- Sequence gap detection and snapshot refresh
- BBO-only mode (fast path)
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from exchanges.logger import setup_logger

from .base import WebsocketClient

logger = setup_logger("ws.lighter")


class LighterWS(WebsocketClient):
    """Lighter WS client for market data + account orders."""

    def __init__(
        self,
        market_index: int,
        on_event: Callable,
        *,
        account_index: Optional[int] = None,
        lighter_client: Optional[Any] = None,
        api_key_index: int = 0,
        ws_url: str = "wss://mainnet.zklighter.elliot.ai/stream",
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 30.0,
        bbo_only: bool = False,
        depth_levels: int = 20,
    ) -> None:
        self.market_index = market_index
        self.account_index = account_index
        self.lighter_client = lighter_client
        self.api_key_index = api_key_index
        self.max_reconnect_delay = max_reconnect_delay
        self.bbo_only = bbo_only
        self.depth_levels = max(1, int(depth_levels))

        self.order_book = {"bids": {}, "asks": {}}
        self.best_bid: Optional[float] = None
        self.best_ask: Optional[float] = None
        self.best_bid_size: Optional[float] = None
        self.best_ask_size: Optional[float] = None
        self.snapshot_loaded = False
        self.order_book_offset: Optional[int] = None
        self.order_book_sequence_gap = False
        self.order_book_lock = asyncio.Lock()
        self.ws = None
        self.max_offset_skip = 5
        self._last_refresh_ts: float = 0.0
        self._log_account_order_keys = (
            os.getenv("LIGHTER_WS_LOG_ORDER_KEYS", "").strip().lower() in ("1", "true", "yes", "y")
        )

        self.cleanup_counter = 0
        self.max_levels = 100

        super().__init__(
            name="lighter",
            stream_url=ws_url,
            on_event=on_event,
            reconnect_delay=reconnect_delay,
        )

    def _clear_order_book_state(self) -> None:
        self.order_book["bids"].clear()
        self.order_book["asks"].clear()
        self.snapshot_loaded = False
        self.best_bid = None
        self.best_ask = None
        self.best_bid_size = None
        self.best_ask_size = None
        self.order_book_offset = None
        self.order_book_sequence_gap = False
        self.cleanup_counter = 0

    async def on_connect(self, ws) -> None:
        self.ws = ws
        async with self.order_book_lock:
            self._clear_order_book_state()

    async def on_disconnect(self) -> None:
        self.ws = None
        async with self.order_book_lock:
            self._clear_order_book_state()

    async def subscribe(self, ws) -> None:
        await ws.send(json.dumps({"type": "subscribe", "channel": f"order_book/{self.market_index}"}))
        logger.info("Subscribed to order_book/%s", self.market_index)

        if self.account_index is not None and self.lighter_client:
            try:
                auth_token, err = self.lighter_client.create_auth_token_with_expiry()
                if err is not None:
                    logger.warning("Failed to create auth token: %s", err)
                else:
                    auth_message = {
                        "type": "subscribe",
                        "channel": f"account_orders/{self.market_index}/{self.account_index}",
                        "auth": auth_token,
                    }
                    await ws.send(json.dumps(auth_message))
                logger.info("Subscribed to account_orders (expires in 10 minutes)")
            except (OSError, ValueError, TypeError) as exc:
                logger.warning("Error subscribing to account orders: %s", exc)

    def _derive_fill_fields(self, order: Dict[str, Any]) -> Dict[str, Any]:
        try:
            filled_base = order.get("filled_base_amount")
            filled_quote = order.get("filled_quote_amount")
            if filled_base is None or filled_quote is None:
                return {}
            filled_amount = float(filled_base)
            if filled_amount == 0:
                return {}
            fill_price = float(filled_quote) / filled_amount
        except (TypeError, ValueError, ZeroDivisionError):
            return {}
        return {"fill_price": fill_price, "filled_amount": filled_amount}

    def _update_order_book(self, side: str, updates: List[Dict[str, Any]]) -> None:
        if side not in ("bids", "asks"):
            return
        if self.bbo_only:
            self._update_bbo_only(side, updates)
            return
        ob = self.order_book[side]
        for update in updates:
            if not isinstance(update, dict):
                continue
            if "price" not in update or "size" not in update:
                continue
            try:
                price = float(update["price"])
                size = float(update["size"])
            except (KeyError, ValueError, TypeError):
                continue
            if price <= 0 or size < 0:
                continue
            if size == 0:
                ob.pop(price, None)
            else:
                ob[price] = size

    def _update_bbo_only(self, side: str, updates: List[Dict[str, Any]]) -> None:
        current_best = self.best_bid if side == "bids" else self.best_ask
        removed_current = False
        best_price = None
        best_size = None

        for update in updates:
            if not isinstance(update, dict):
                continue
            if "price" not in update or "size" not in update:
                continue
            try:
                price = float(update["price"])
                size = float(update["size"])
            except (KeyError, ValueError, TypeError):
                continue
            if price <= 0 or size < 0:
                continue

            if size == 0 and current_best is not None and price == current_best:
                removed_current = True
                continue
            if size == 0:
                continue

            if best_price is None:
                best_price, best_size = price, size
            elif side == "bids":
                if price > best_price:
                    best_price, best_size = price, size
                elif price == best_price:
                    best_size = size
            else:
                if price < best_price:
                    best_price, best_size = price, size
                elif price == best_price:
                    best_size = size

        if best_price is not None:
            if side == "bids":
                self.best_bid = best_price
                self.best_bid_size = best_size
            else:
                self.best_ask = best_price
                self.best_ask_size = best_size
        elif removed_current:
            if side == "bids":
                self.best_bid = None
                self.best_bid_size = None
            else:
                self.best_ask = None
                self.best_ask_size = None

    def _validate_order_book_offset(self, new_offset: int) -> bool:
        if self.bbo_only:
            if self.order_book_offset is None or new_offset > self.order_book_offset:
                self.order_book_offset = new_offset
            else:
                logger.debug("Ignore out-of-order offset %s (current %s)", new_offset, self.order_book_offset)
            self.order_book_sequence_gap = False
            return True

        if self.order_book_offset is None:
            self.order_book_offset = new_offset
            return True

        expected_offset = self.order_book_offset + 1
        if new_offset <= self.order_book_offset:
            logger.debug("Ignore out-of-order offset %s (current %s)", new_offset, self.order_book_offset)
            return True
        if new_offset == expected_offset:
            self.order_book_offset = new_offset
            self.order_book_sequence_gap = False
            return True

        if new_offset > expected_offset and (new_offset - expected_offset) <= self.max_offset_skip:
            logger.debug(
                "Sequence jump tolerated (expected %s, got %s)", expected_offset, new_offset
            )
            self.order_book_offset = new_offset
            self.order_book_sequence_gap = False
            return True

        logger.warning("Sequence gap detected! expected=%s got=%s", expected_offset, new_offset)
        self.order_book_sequence_gap = True
        return False

    def _validate_order_book_integrity(self) -> bool:
        try:
            if self.bbo_only:
                if self.best_bid is None or self.best_ask is None:
                    return True
                if self.best_bid >= self.best_ask:
                    logger.warning(
                        "Order book inconsistency best_bid=%s best_ask=%s",
                        self.best_bid,
                        self.best_ask,
                    )
                    return False
                return True

            if not self.order_book["bids"] or not self.order_book["asks"]:
                return True

            best_bid = max(self.order_book["bids"].keys())
            best_ask = min(self.order_book["asks"].keys())
            if best_bid >= best_ask:
                logger.warning(
                    "Order book inconsistency best_bid=%s best_ask=%s",
                    best_bid,
                    best_ask,
                )
                return False
            return True
        except (ValueError, TypeError, KeyError) as exc:
            logger.error("Order book validation error: %s", exc)
            return False

    def _get_best_levels(self) -> Tuple[Tuple[Optional[float], Optional[float]], Tuple[Optional[float], Optional[float]]]:
        try:
            if self.bbo_only:
                return (self.best_bid, self.best_bid_size), (self.best_ask, self.best_ask_size)

            bid_levels = list(self.order_book["bids"].items())
            ask_levels = list(self.order_book["asks"].items())
            best_bid = max(bid_levels) if bid_levels else (None, None)
            best_ask = min(ask_levels) if ask_levels else (None, None)
            return best_bid, best_ask
        except (ValueError, TypeError, KeyError) as exc:
            logger.error("Best level extraction error: %s", exc)
            return (None, None), (None, None)

    def _cleanup_old_levels(self) -> None:
        if self.bbo_only:
            return
        try:
            if len(self.order_book["bids"]) > self.max_levels:
                sorted_bids = sorted(self.order_book["bids"].items(), reverse=True)
                self.order_book["bids"].clear()
                for price, size in sorted_bids[: self.max_levels]:
                    self.order_book["bids"][price] = size
            if len(self.order_book["asks"]) > self.max_levels:
                sorted_asks = sorted(self.order_book["asks"].items())
                self.order_book["asks"].clear()
                for price, size in sorted_asks[: self.max_levels]:
                    self.order_book["asks"][price] = size
        except (ValueError, TypeError, KeyError) as exc:
            logger.error("Order book cleanup error: %s", exc)

    async def _send_pong(self) -> None:
        if not self.ws:
            return
        try:
            await self.ws.send(json.dumps({"type": "pong"}))
        except (OSError, TypeError, ValueError) as exc:
            logger.debug("Failed to send pong: %s", exc)

    async def _request_fresh_snapshot(self) -> None:
        now = time.time()
        if now - self._last_refresh_ts < 1.0:
            logger.debug("Snapshot refresh throttled")
            return
        self._last_refresh_ts = now
        if not self.ws:
            logger.warning("Cannot refresh snapshot: no active websocket")
            return

        try:
            async with self.order_book_lock:
                self._clear_order_book_state()
                ws = self.ws
            if not ws:
                logger.warning("WebSocket became None during snapshot refresh")
                return
            await ws.send(
                json.dumps({"type": "unsubscribe", "channel": f"order_book/{self.market_index}"})
            )
            await asyncio.sleep(0.5)
            await ws.send(
                json.dumps({"type": "subscribe", "channel": f"order_book/{self.market_index}"})
            )
            logger.info("Requested fresh order book snapshot")
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Failed to refresh snapshot, closing websocket: %s", exc)
            try:
                await self.ws.close()
            except (OSError, TypeError):
                pass

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("JSON parsing error: %s", exc)
            return

        msg_type = data.get("type")
        if msg_type == "ping":
            await self._send_pong()
            return

        event = None
        need_snapshot_refresh = False

        async with self.order_book_lock:
            if msg_type == "subscribed/order_book":
                self._clear_order_book_state()
                order_book = data.get("order_book", {})
                if order_book and "offset" in order_book:
                    self.order_book_offset = order_book.get("offset")
                    logger.info("Initial order book offset: %s", self.order_book_offset)
                self._update_order_book("bids", order_book.get("bids", []))
                self._update_order_book("asks", order_book.get("asks", []))
                self.snapshot_loaded = True

            elif msg_type == "update/order_book" and self.snapshot_loaded:
                order_book = data.get("order_book", {})
                if not order_book or "offset" not in order_book:
                    logger.warning("Order book update missing offset")
                    need_snapshot_refresh = True
                else:
                    new_offset = order_book.get("offset")
                    if not self._validate_order_book_offset(new_offset):
                        need_snapshot_refresh = True
                    else:
                        self._update_order_book("bids", order_book.get("bids", []))
                        self._update_order_book("asks", order_book.get("asks", []))

                        if self.bbo_only and (self.best_bid is None or self.best_ask is None):
                            logger.warning("Best level missing after update")
                            need_snapshot_refresh = True

                        if not self._validate_order_book_integrity():
                            logger.warning("Order book integrity failed")
                            need_snapshot_refresh = True
                        else:
                            (best_bid_price, best_bid_size), (best_ask_price, best_ask_size) = (
                                self._get_best_levels()
                            )

                            if best_bid_price is not None:
                                self.best_bid = best_bid_price
                                self.best_bid_size = best_bid_size
                            if best_ask_price is not None:
                                self.best_ask = best_ask_price
                                self.best_ask_size = best_ask_size

                            if not need_snapshot_refresh:
                                symbol = (
                                    order_book.get("code")
                                    or data.get("symbol")
                                    or f"MARKET_{self.market_index}"
                                )
                                ts_exchange = (
                                    order_book.get("timestamp")
                                    or order_book.get("ts")
                                    or data.get("timestamp")
                                    or ts_local_ms
                                )

                                bids = []
                                asks = []
                                if self.bbo_only:
                                    if best_bid_price is not None:
                                        bids = [[best_bid_price, best_bid_size]]
                                    if best_ask_price is not None:
                                        asks = [[best_ask_price, best_ask_size]]
                                else:
                                    bids = [
                                        [p, s]
                                        for p, s in sorted(self.order_book["bids"].items(), reverse=True)[
                                            : self.depth_levels
                                        ]
                                    ]
                                    asks = [
                                        [p, s]
                                        for p, s in sorted(self.order_book["asks"].items())[ : self.depth_levels]
                                    ]

                                event = {
                                    "exchange": "lighter",
                                    "symbol": symbol,
                                    "stream": "bbo" if self.bbo_only else "l2",
                                    "market_index": self.market_index,
                                    "ts_exchange": ts_exchange,
                                    "ts_local": ts_local_ms,
                                    "best_bid": best_bid_price,
                                    "best_ask": best_ask_price,
                                    "best_bid_size": best_bid_size,
                                    "best_ask_size": best_ask_size,
                                    "bids": bids,
                                    "asks": asks,
                                    "raw": data,
                                }

                            self.cleanup_counter += 1
                            if self.cleanup_counter >= 1000:
                                self._cleanup_old_levels()
                                self.cleanup_counter = 0

            elif msg_type == "update/account_orders":
                orders = data.get("orders", {}).get(str(self.market_index), [])
                enriched_orders = []
                for order in orders or []:
                    if (
                        self._log_account_order_keys
                        and isinstance(order, dict)
                        and logger.isEnabledFor(logging.DEBUG)
                    ):
                        try:
                            logger.debug("lighter account_orders keys: %s", sorted(order.keys()))
                        except (TypeError, AttributeError):
                            pass
                    if isinstance(order, dict):
                        derived = self._derive_fill_fields(order)
                        if derived:
                            order = {**order, **derived}
                    enriched_orders.append(order)

                event = {
                    "exchange": "lighter",
                    "stream": "account_orders",
                    "market_index": self.market_index,
                    "ts_exchange": data.get("timestamp") or data.get("ts") or ts_local_ms,
                    "ts_local": ts_local_ms,
                    "orders": enriched_orders,
                    "raw": data,
                }

            # Emit event while still holding the lock to prevent race conditions
            if event:
                await self.on_event(event)

        if need_snapshot_refresh:
            await self._request_fresh_snapshot()

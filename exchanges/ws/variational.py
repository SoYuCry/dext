"""Variational (Omni) RFQ price/fill streams."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Iterable, Optional
from urllib.parse import quote

from .base import WebsocketClient
from ..variational import VariationalClient
from exchanges.logger import setup_logger

logger = setup_logger("ws.variational")


class VariationalPricePoller:
    """Poll indicative quotes as a stand-in for a live price stream."""

    def __init__(
        self,
        client: VariationalClient,
        instrument: Dict[str, Any],
        qty: Any,
        on_event,
        *,
        interval: float = 1.0,
    ) -> None:
        self.client = client
        self.instrument = instrument
        self.qty = qty
        self.on_event = on_event
        self.interval = interval
        self._stop = asyncio.Event()
        self._last_success_ts: Optional[int] = None

    async def stop(self) -> None:
        self._stop.set()

    async def _fetch_quote(self) -> Optional[Dict[str, Any]]:
        start = time.time()
        try:
            quote_resp = await asyncio.to_thread(
                self.client.request_indicative_quote,
                self.qty,
                instrument=self.instrument,
            )
        except Exception as exc:  # noqa
            logger.warning("Variational quote poll failed: %s", exc)
            return None
        latency_ms = int((time.time() - start) * 1000)
        slow_warn_ms = int(max(1000.0, self.interval * 1000.0 * 1.5))
        if latency_ms > slow_warn_ms:
            logger.warning("Variational quote slow latency_ms=%s", latency_ms)
        return {"resp": quote_resp, "latency_ms": latency_ms}

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            cycle_start = time.monotonic()
            try:
                result = await self._fetch_quote()
            except Exception as exc:  # noqa
                logger.warning("Variational quote task failed: %s", exc)
                result = None
            if result:
                quote_resp = result["resp"]
                latency_ms = result["latency_ms"]
                if not getattr(quote_resp, "success", False):
                    logger.debug("Variational quote error: %s", getattr(quote_resp, "error_message", "unknown"))
                else:
                    data = getattr(quote_resp, "data", {}) or {}
                    quote_id = data.get("quote_id")
                    raw = data.get("raw") or data
                    bid = data.get("bid")
                    ask = data.get("ask")
                    if bid is None or ask is None:
                        logger.warning("Variational quote missing bid/ask: %s", raw)
                        bid = ask = None

                    now_ms = int(time.time() * 1000)
                    if self._last_success_ts is not None:
                        gap_ms = int(now_ms - self._last_success_ts)
                        gap_warn_ms = int(max(1500.0, self.interval * 1000.0 * 2.5))
                        if gap_ms > gap_warn_ms:
                            logger.warning("Variational quote gap gap_ms=%s", gap_ms)
                    self._last_success_ts = now_ms

                    if bid is not None and ask is not None:
                        event = {
                            "exchange": "variational",
                            "stream": "rfq_quote",
                            "bid": bid,
                            "ask": ask,
                            "quote_id": quote_id,
                            "instrument": self.instrument,
                            "ts_local": now_ms,
                            "latency_ms": latency_ms,
                            "raw": raw,
                        }
                        await self.on_event(event)

            elapsed = time.monotonic() - cycle_start
            sleep_s = max(0.0, self.interval - elapsed)
            if sleep_s:
                await asyncio.sleep(sleep_s)


class VariationalFillPoller:
    """Poll transfers to surface new fills."""

    def __init__(
        self,
        client: VariationalClient,
        on_event,
        *,
        limit: int = 50,
        interval: float = 2.0,
    ) -> None:
        self.client = client
        self.on_event = on_event
        self.limit = limit
        self.interval = interval
        self._seen_ids = set()
        self._stop = asyncio.Event()

    async def stop(self) -> None:
        self._stop.set()

    def _extract_items(self, payload: Any) -> Iterable[Dict[str, Any]]:
        if payload is None:
            return []
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("transfers", "data", "items", "results"):
                if key in payload and isinstance(payload[key], list):
                    return payload[key]
        return []

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                resp = await asyncio.to_thread(self.client.fetch_trades, None, self.limit)
            except Exception as exc:  # noqa
                logger.warning("Variational fill poll failed: %s", exc)
                await asyncio.sleep(self.interval)
                continue

            payload = resp.data if hasattr(resp, "data") else resp
            for item in self._extract_items(payload):
                transfer_id = item.get("transfer_id") or item.get("id")
                if not transfer_id or transfer_id in self._seen_ids:
                    continue
                self._seen_ids.add(transfer_id)
                event = {
                    "exchange": "variational",
                    "stream": "fills",
                    "event_type": "FILL_UPDATE",
                    "transfer_id": transfer_id,
                    "ts_local": int(time.time() * 1000),
                    "raw": item,
                }
                await self.on_event(event)

            await asyncio.sleep(self.interval)


def _format_instrument_symbol(instrument: Any) -> str:
    if isinstance(instrument, dict):
        underlying = instrument.get("underlying")
        settle = instrument.get("settlement_asset")
        itype = instrument.get("instrument_type") or ""
        if underlying and settle:
            suffix = "_PERP" if "perp" in itype else ""
            return f"{underlying}_{settle}{suffix}"
    return str(instrument or "")


class VariationalEventsWS(WebsocketClient):
    """WebSocket event stream (trade/fill/portfolio updates)."""

    def __init__(
        self,
        on_event,
        *,
        ws_url: str = "wss://omni-ws-server.prod.ap-northeast-1.variational.io/events",
        auth_token: Optional[str] = None,
        query_params: Optional[str] = None,
        claims_token: Optional[str] = None,
        cookie: Optional[str] = None,
        origin: str = "https://omni.variational.io",
        reconnect_delay: float = 3.0,
    ) -> None:
        self.base_url = ws_url
        self.auth_token = auth_token
        self.query_params = query_params
        self.claims_token = claims_token
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        if origin:
            headers["Origin"] = origin
        extra_headers = headers or None
        super().__init__(
            name="variational-events",
            stream_url=ws_url,
            on_event=on_event,
            reconnect_delay=reconnect_delay,
            extra_headers=extra_headers,
        )

    async def get_stream_url(self) -> str:
        url = self.base_url
        if self.query_params:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{self.query_params}"
        if self.auth_token and "auth=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}auth={quote(self.auth_token)}"
        return url

    async def subscribe(self, ws) -> None:
        if self.claims_token:
            await ws.send('{"claims":"%s"}' % self.claims_token.replace('"', '\\"'))

    async def handle_message(self, raw: str, ts_local_ms: int) -> None:
        try:
            msg = self.decode(raw)
        except Exception:
            return

        event_type = msg.get("type")
        data = msg.get("data") or {}
        if not event_type:
            return

        event = {
            "exchange": "variational",
            "stream": "events",
            "event_type": event_type,
            "ts_local": ts_local_ms,
            "raw": msg,
        }

        if event_type == "trade" and isinstance(data, dict):
            event.update(
                {
                    "trade_id": data.get("id"),
                    "side": data.get("side"),
                    "price": data.get("price"),
                    "qty": data.get("qty"),
                    "symbol": _format_instrument_symbol(data.get("instrument")),
                    "mark_price": data.get("mark_price"),
                    "created_at": data.get("created_at"),
                    "role": data.get("role"),
                }
            )

        await self.on_event(event)

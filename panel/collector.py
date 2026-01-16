"""Data collector - subscribe to user WebSocket streams and poll positions."""
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path to import api module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.ws import get_user_ws_client
from api import get_client
from .config import (
    ASTER_API_KEY,
    ASTER_SECRET,
    BACKPACK_API_KEY,
    BACKPACK_SECRET,
    ASTER_SYMBOL,
    BACKPACK_SYMBOL,
    POSITION_UPDATE_INTERVAL,
    ORDER_UPDATE_INTERVAL,
)


class DataCollector:
    """Collect real-time data from Aster and Backpack via WebSocket and REST API."""

    def __init__(self, on_update_callback=None):
        self.on_update = on_update_callback

        # State
        self.aster_orders: List[Dict[str, Any]] = []
        self.backpack_orders: List[Dict[str, Any]] = []
        self.aster_fills: List[Dict[str, Any]] = []
        self.backpack_fills: List[Dict[str, Any]] = []
        self.aster_position: Optional[Dict[str, Any]] = None
        self.backpack_position: Optional[Dict[str, Any]] = None

        # WebSocket clients
        self.aster_ws = None
        self.backpack_ws = None

        # REST clients (for polling positions and open orders)
        self.aster_client = None
        self.backpack_client = None

        # Tasks
        self.tasks = []
        self._stop = asyncio.Event()

    async def start(self):
        """Start WebSocket subscriptions and polling tasks."""
        # Initialize REST clients
        self.aster_client = get_client("aster", {"apiKey": ASTER_API_KEY, "secret": ASTER_SECRET})
        self.backpack_client = get_client("backpack", {"apiKey": BACKPACK_API_KEY, "secret": BACKPACK_SECRET})

        # Start WebSocket subscriptions for user data (orders and fills)
        self.aster_ws = get_user_ws_client("aster", self._on_aster_event, api_key=ASTER_API_KEY)
        self.backpack_ws = get_user_ws_client(
            "backpack",
            self._on_backpack_event,
            api_key=BACKPACK_API_KEY,
            secret=BACKPACK_SECRET,
        )

        # Start tasks
        self.tasks = [
            asyncio.create_task(self.aster_ws.run_forever(), name="aster-ws"),
            asyncio.create_task(self.backpack_ws.run_forever(), name="backpack-ws"),
            asyncio.create_task(self._poll_positions(), name="poll-positions"),
            asyncio.create_task(self._poll_orders(), name="poll-orders"),
        ]

        print(f"[DataCollector] Started - monitoring {ASTER_SYMBOL} (Aster) and {BACKPACK_SYMBOL} (Backpack)")

    async def stop(self):
        """Stop all tasks and WebSocket connections."""
        self._stop.set()
        for task in self.tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.tasks = []

    async def _on_aster_event(self, event: Dict[str, Any]):
        """Handle Aster user data stream events."""
        event_type = event.get("event_type")

        if event_type == "ORDER_TRADE_UPDATE":
            # Update order list
            order_id = event.get("order_id")
            existing = next((o for o in self.aster_orders if o.get("order_id") == order_id), None)
            if existing:
                existing.update(event)
            else:
                self.aster_orders.append(event)

            # Remove filled/cancelled orders
            self.aster_orders = [
                o for o in self.aster_orders
                if o.get("status") not in ["Filled", "Cancelled", "Canceled", "FILLED", "CANCELLED", "NEW_INSURANCE", "NEW_ADL"]
            ]

            # If this is a fill, also add to fills history
            execution_type = event.get("execution_type")
            if execution_type == "TRADE":
                self.aster_fills.insert(0, event)
                self.aster_fills = self.aster_fills[:50]

        await self._notify_update()

    async def _on_backpack_event(self, event: Dict[str, Any]):
        """Handle Backpack user data stream events."""
        event_type = event.get("event_type")

        if event_type == "ORDER_UPDATE":
            order_id = event.get("order_id")
            existing = next((o for o in self.backpack_orders if o.get("order_id") == order_id), None)
            if existing:
                existing.update(event)
            else:
                self.backpack_orders.append(event)

            # Remove filled/cancelled orders
            self.backpack_orders = [
                o for o in self.backpack_orders
                if o.get("status") not in ["Filled", "Cancelled", "Canceled", "FILLED", "CANCELLED"]
            ]

        elif event_type == "FILL_UPDATE":
            self.backpack_fills.insert(0, event)
            self.backpack_fills = self.backpack_fills[:50]

        await self._notify_update()

    async def _poll_positions(self):
        """Poll positions from both exchanges periodically."""
        await asyncio.sleep(2)  # Initial delay

        while not self._stop.is_set():
            try:
                # Fetch Aster position (using REST API)
                aster_balance = await asyncio.to_thread(self.aster_client.fetch_balance)
                # Extract position for the symbol (simplified)
                self.aster_position = {
                    "total_balance": aster_balance.get("total", {}),
                    "free": aster_balance.get("free", {}),
                    "used": aster_balance.get("used", {}),
                    "timestamp": datetime.now().isoformat(),
                }

                # Fetch Backpack position
                backpack_balance = await asyncio.to_thread(self.backpack_client.fetch_balance)
                self.backpack_position = {
                    "total_balance": backpack_balance.get("total", {}),
                    "free": backpack_balance.get("free", {}),
                    "used": backpack_balance.get("used", {}),
                    "timestamp": datetime.now().isoformat(),
                }

                await self._notify_update()

            except Exception as e:
                print(f"[DataCollector] Error polling positions: {e}")

            await asyncio.sleep(POSITION_UPDATE_INTERVAL)

    async def _poll_orders(self):
        """Poll open orders periodically (backup to WebSocket)."""
        await asyncio.sleep(3)  # Initial delay

        while not self._stop.is_set():
            try:
                # Fetch Aster open orders
                aster_orders = await asyncio.to_thread(
                    self.aster_client.fetch_open_orders,
                    ASTER_SYMBOL
                )

                # Fetch Backpack open orders
                backpack_orders = await asyncio.to_thread(
                    self.backpack_client.fetch_open_orders,
                    BACKPACK_SYMBOL
                )

                # Update order lists (merge with WebSocket data)
                # This is a backup mechanism in case WebSocket misses updates
                # For simplicity, we trust WebSocket data more

            except Exception as e:
                print(f"[DataCollector] Error polling orders: {e}")

            await asyncio.sleep(ORDER_UPDATE_INTERVAL)

    async def _notify_update(self):
        """Notify callback of data update."""
        if self.on_update:
            await self.on_update(self.get_state())

    def get_state(self) -> Dict[str, Any]:
        """Get current state snapshot."""
        return {
            "timestamp": datetime.now().isoformat(),
            "aster": {
                "orders": self.aster_orders,
                "fills": self.aster_fills[:10],  # Latest 10 fills
                "position": self.aster_position,
            },
            "backpack": {
                "orders": self.backpack_orders,
                "fills": self.backpack_fills[:10],
                "position": self.backpack_position,
            },
        }

"""Standardized data type definitions

This module defines the standardized format for all WebSocket data.
All exchange-specific raw data is converted into these standard types.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional
from enum import Enum


# ==================== Enum Definitions ====================

class OrderStatus(str, Enum):
    """Standardized order status"""
    OPEN = "OPEN"                          # New order, unfilled
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Partially filled
    FILLED = "FILLED"                      # Fully filled
    CANCELLED = "CANCELLED"                # Cancelled
    REJECTED = "REJECTED"                  # Rejected
    EXPIRED = "EXPIRED"                    # Expired


class OrderSide(str, Enum):
    """Standardized order side"""
    BUY = "buy"
    SELL = "sell"


class EventType(str, Enum):
    """Event type"""
    BBO_UPDATE = "BBO_UPDATE"      # Best bid/offer update
    L2_UPDATE = "L2_UPDATE"        # L2 order book update
    ORDER_UPDATE = "ORDER_UPDATE"  # Order status update
    FILL_UPDATE = "FILL_UPDATE"    # Fill update


# ==================== Data Classes ====================

@dataclass
class BBOData:
    """BBO core data

    Contains best bid/offer prices and derived computed properties.
    """
    bid: Decimal          # Best bid price
    ask: Decimal          # Best ask price
    bid_size: Decimal     # Best bid size
    ask_size: Decimal     # Best ask size
    last_price: Optional[Decimal] = None  # Last trade price (if provided by exchange)

    @property
    def mid(self) -> Decimal:
        """Mid price = (bid + ask) / 2"""
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> Decimal:
        """Spread = ask - bid"""
        return self.ask - self.bid

    @property
    def spread_bps(self) -> Decimal:
        """Spread in basis points = (spread / mid) * 10000"""
        mid = self.mid
        if mid > 0:
            return (self.spread / mid) * 10000
        return Decimal(0)

    def __str__(self) -> str:
        return f"BBO(bid={self.bid}, ask={self.ask}, spread={self.spread_bps:.2f}bps)"


@dataclass
class EventMetadata:
    """Event metadata

    Contains timestamp and event type information.
    """
    ts_exchange: int      # Exchange timestamp (milliseconds)
    ts_local: int         # Local receive timestamp (milliseconds)
    event_type: EventType # Event type

    @property
    def latency_ms(self) -> int:
        """Latency (ms) = ts_local - ts_exchange"""
        return self.ts_local - self.ts_exchange

    def __str__(self) -> str:
        return f"Meta(type={self.event_type.value}, latency={self.latency_ms}ms)"


@dataclass
class BBOUpdate:
    """Standardized BBO update event

    This is the standardized market data format received by strategies.
    All exchange BBO data is converted into this format.
    """
    exchange: str                         # Exchange name (lowercase)
    symbol: str                          # Standardized trading pair symbol (e.g. "ETH/USDC")
    data: BBOData                        # BBO data
    metadata: EventMetadata              # Metadata
    raw: Optional[Dict[str, Any]] = None # Raw data (for debugging)

    def __str__(self) -> str:
        return f"BBOUpdate({self.exchange} {self.symbol}: {self.data})"


@dataclass
class OrderData:
    """Order core data"""
    order_id: str                           # Exchange order ID
    client_order_id: Optional[str]          # Client order ID
    status: OrderStatus                     # Standardized status
    side: OrderSide                         # Buy/sell side
    price: Optional[Decimal]                # Order price (None for market orders)
    amount: Decimal                         # Total order quantity
    filled: Decimal                         # Filled quantity
    remaining: Decimal                      # Remaining quantity

    # Fill info (only present for FILL_UPDATE events)
    fill_price: Optional[Decimal] = None    # This fill's price
    filled_amount: Optional[Decimal] = None # This fill's quantity

    def __str__(self) -> str:
        return (
            f"Order(id={self.order_id}, status={self.status.value}, "
            f"side={self.side.value}, filled={self.filled}/{self.amount})"
        )


@dataclass
class OrderUpdate:
    """Standardized order update event

    This is the standardized order data format received by strategies.
    Contains order status changes and fill information.
    """
    exchange: str                         # Exchange name (lowercase)
    symbol: str                          # Standardized trading pair symbol
    data: OrderData                      # Order data
    metadata: EventMetadata              # Metadata
    raw: Optional[Dict[str, Any]] = None # Raw data (for debugging)

    def __str__(self) -> str:
        return f"OrderUpdate({self.exchange} {self.symbol}: {self.data})"

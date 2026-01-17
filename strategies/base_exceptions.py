"""Base exceptions for trading strategies.

This module provides a hierarchical exception system for trading strategies
with severity levels and automatic alerting capabilities.
"""

from typing import Any, Dict, Optional
from enum import Enum


class Severity(str, Enum):
    """Exception severity levels."""
    
    CRITICAL = "CRITICAL"  # Must stop strategy immediately
    WARNING = "WARNING"    # Alert but can continue
    INFO = "INFO"          # Just for logging


class StrategyException(Exception):
    """Base exception for all strategy errors.
    
    Attributes:
        severity: Exception severity level
        message: Human-readable error message
        details: Additional context and data
        action: Suggested action (STOP_STRATEGY, PAUSE_QUOTING, CONTINUE, etc.)
    """
    
    severity: Severity = Severity.INFO
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        action: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.action = action or self._default_action()
    
    def _default_action(self) -> str:
        """Get default action based on severity."""
        if self.severity == Severity.CRITICAL:
            return "STOP_STRATEGY"
        elif self.severity == Severity.WARNING:
            return "CONTINUE"
        else:
            return "LOG_ONLY"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/alerting."""
        return {
            "type": self.__class__.__name__,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "action": self.action,
        }


# ============================================================================
# CRITICAL Exceptions - Must stop strategy immediately
# ============================================================================

class CriticalException(StrategyException):
    """Critical error that requires immediate strategy shutdown."""
    
    severity = Severity.CRITICAL


class HedgeFailed(CriticalException):
    """Hedge order failed - creates single-sided exposure.
    
    This is CRITICAL because:
    - Primary position is already opened
    - Hedge failed to execute
    - Creates directional price risk
    - Must stop immediately to prevent further exposure
    
    Args:
        primary_info: Information about the primary position
        hedge_exchange: Name of the hedge exchange
        error: Error message from failed hedge
    """
    
    def __init__(
        self,
        primary_info: Dict[str, Any],
        hedge_exchange: str,
        error: str,
    ):
        message = (
            f"🚨 HEDGE FAILED - SINGLE-SIDED EXPOSURE!\n"
            f"Primary: {primary_info.get('side')} {primary_info.get('qty')} "
            f"@ {primary_info.get('price')}\n"
            f"Hedge on {hedge_exchange} failed: {error}\n"
            f"Strategy MUST stop to prevent further exposure."
        )
        details = {
            "primary_info": primary_info,
            "hedge_exchange": hedge_exchange,
            "error": error,
        }
        super().__init__(message, details, action="STOP_STRATEGY")


class InsufficientMarginCritical(CriticalException):
    """Insufficient margin for critical operations (e.g., hedging).
    
    This is CRITICAL because:
    - Cannot hedge new positions
    - Will create single-sided exposure
    - Must stop before opening more positions
    
    Args:
        exchange: Exchange name
        operation: Operation that failed (e.g., "hedge", "close_position")
        required: Required margin amount
        available: Available margin amount
    """
    
    def __init__(
        self,
        exchange: str,
        operation: str,
        required: float,
        available: float,
    ):
        message = (
            f"🚨 INSUFFICIENT MARGIN FOR {operation.upper()}!\n"
            f"Exchange: {exchange}\n"
            f"Required: ${required:.2f}\n"
            f"Available: ${available:.2f}\n"
            f"Cannot execute {operation} - stopping strategy."
        )
        details = {
            "exchange": exchange,
            "operation": operation,
            "required": required,
            "available": available,
            "shortfall": required - available,
        }
        super().__init__(message, details, action="STOP_STRATEGY")


class PositionImbalance(CriticalException):
    """Position imbalance detected between exchanges.
    
    This is CRITICAL because:
    - Indicates hedge failures or missed fills
    - Creates directional risk
    - Needs immediate attention
    
    Args:
        positions: Dictionary of exchange -> position
        threshold: Imbalance threshold that was exceeded
    """
    
    def __init__(
        self,
        positions: Dict[str, float],
        threshold: float,
    ):
        total = sum(positions.values())
        imbalance = abs(total)
        message = (
            f"🚨 POSITION IMBALANCE DETECTED!\n"
            f"Positions: {positions}\n"
            f"Total: {total:.4f}\n"
            f"Imbalance: {imbalance:.4f} (threshold: {threshold:.4f})\n"
            f"Stopping strategy for manual review."
        )
        details = {
            "positions": positions,
            "total": total,
            "imbalance": imbalance,
            "threshold": threshold,
        }
        super().__init__(message, details, action="STOP_STRATEGY")


class ExchangeConnectionLost(CriticalException):
    """Critical exchange connection lost.
    
    This is CRITICAL because:
    - Cannot monitor positions
    - Cannot execute orders
    - Risk of missed fills or unhedged positions
    
    Args:
        exchange: Exchange name
        connection_type: Type of connection (e.g., "websocket", "rest")
        duration_seconds: How long connection has been lost
    """
    
    def __init__(
        self,
        exchange: str,
        connection_type: str,
        duration_seconds: float,
    ):
        message = (
            f"🚨 EXCHANGE CONNECTION LOST!\n"
            f"Exchange: {exchange}\n"
            f"Type: {connection_type}\n"
            f"Duration: {duration_seconds:.1f}s\n"
            f"Cannot operate safely - stopping strategy."
        )
        details = {
            "exchange": exchange,
            "connection_type": connection_type,
            "duration_seconds": duration_seconds,
        }
        super().__init__(message, details, action="STOP_STRATEGY")


# ============================================================================
# WARNING Exceptions - Should alert but can continue
# ============================================================================

class WarningException(StrategyException):
    """Warning that should be logged and alerted, but strategy can continue."""
    
    severity = Severity.WARNING


class OrderFailed(WarningException):
    """Order failed to execute.
    
    This is WARNING because:
    - Reduces strategy effectiveness
    - But doesn't create directional risk (if not a hedge)
    - Strategy can continue with degraded performance
    
    Args:
        exchange: Exchange name
        order_type: Type of order (e.g., "quote", "close")
        side: Order side (buy/sell)
        amount: Order amount
        price: Order price (if applicable)
        error: Error message
    """
    
    def __init__(
        self,
        exchange: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float],
        error: str,
    ):
        price_str = f" @ {price:.2f}" if price else ""
        message = (
            f"⚠️ {order_type.upper()} ORDER FAILED\n"
            f"Exchange: {exchange}\n"
            f"Order: {side} {amount:.4f}{price_str}\n"
            f"Error: {error}"
        )
        details = {
            "exchange": exchange,
            "order_type": order_type,
            "side": side,
            "amount": amount,
            "price": price,
            "error": error,
        }
        super().__init__(message, details, action="CONTINUE")


class InsufficientMarginWarning(WarningException):
    """Insufficient margin for non-critical operations.
    
    This is WARNING because:
    - Cannot place new orders
    - But existing positions are safe
    - Can pause and wait for margin
    
    Args:
        exchange: Exchange name
        operation: Operation that failed (e.g., "quote")
        required: Required margin amount
        available: Available margin amount
    """
    
    def __init__(
        self,
        exchange: str,
        operation: str,
        required: float,
        available: float,
    ):
        message = (
            f"⚠️ Insufficient margin for {operation}\n"
            f"Exchange: {exchange}\n"
            f"Required: ${required:.2f}\n"
            f"Available: ${available:.2f}\n"
            f"Pausing {operation} until margin available..."
        )
        details = {
            "exchange": exchange,
            "operation": operation,
            "required": required,
            "available": available,
            "shortfall": required - available,
        }
        super().__init__(message, details, action="PAUSE_OPERATION")


class HighFailureRate(WarningException):
    """High failure rate detected for operations.
    
    This is WARNING because:
    - Indicates systematic issue
    - But strategy can continue with reduced effectiveness
    - Needs investigation
    
    Args:
        operation: Operation type (e.g., "quote_orders")
        failed: Number of failed operations
        total: Total number of operations
        threshold: Failure rate threshold
    """
    
    def __init__(
        self,
        operation: str,
        failed: int,
        total: int,
        threshold: float,
    ):
        failure_rate = failed / total if total > 0 else 0
        message = (
            f"⚠️ High {operation} failure rate\n"
            f"Failed: {failed}/{total} ({failure_rate*100:.1f}%)\n"
            f"Threshold: {threshold*100:.1f}%\n"
            f"Continuing with degraded performance..."
        )
        details = {
            "operation": operation,
            "failed": failed,
            "total": total,
            "failure_rate": failure_rate,
            "threshold": threshold,
        }
        super().__init__(message, details, action="CONTINUE")


class PriceFeedStale(WarningException):
    """Price feed data is stale.
    
    This is WARNING because:
    - May lead to bad quotes
    - But can pause quoting until feed recovers
    - Existing positions are safe
    
    Args:
        exchange: Exchange name
        feed_type: Type of feed (e.g., "orderbook", "ticker")
        last_update_seconds: Seconds since last update
        threshold_seconds: Staleness threshold
    """
    
    def __init__(
        self,
        exchange: str,
        feed_type: str,
        last_update_seconds: float,
        threshold_seconds: float,
    ):
        message = (
            f"⚠️ Price feed stale\n"
            f"Exchange: {exchange}\n"
            f"Feed: {feed_type}\n"
            f"Last update: {last_update_seconds:.1f}s ago\n"
            f"Threshold: {threshold_seconds:.1f}s\n"
            f"Pausing operations until feed recovers..."
        )
        details = {
            "exchange": exchange,
            "feed_type": feed_type,
            "last_update_seconds": last_update_seconds,
            "threshold_seconds": threshold_seconds,
        }
        super().__init__(message, details, action="PAUSE_OPERATION")


# ============================================================================
# INFO Exceptions - Just for logging
# ============================================================================

class InfoException(StrategyException):
    """Informational exception, no action needed."""
    
    severity = Severity.INFO


class OrderPartiallyFilled(InfoException):
    """Order was partially filled.
    
    Args:
        order_id: Order ID
        filled: Filled amount
        total: Total order amount
    """
    
    def __init__(self, order_id: str, filled: float, total: float):
        message = f"ℹ️ Order {order_id} partially filled: {filled}/{total}"
        details = {
            "order_id": order_id,
            "filled": filled,
            "total": total,
            "remaining": total - filled,
        }
        super().__init__(message, details, action="LOG_ONLY")


class StrategyPaused(InfoException):
    """Strategy was paused.
    
    Args:
        reason: Reason for pause
    """
    
    def __init__(self, reason: str):
        message = f"ℹ️ Strategy paused: {reason}"
        details = {"reason": reason}
        super().__init__(message, details, action="LOG_ONLY")


class StrategyResumed(InfoException):
    """Strategy was resumed.
    
    Args:
        reason: Reason for resume
    """
    
    def __init__(self, reason: str):
        message = f"ℹ️ Strategy resumed: {reason}"
        details = {"reason": reason}
        super().__init__(message, details, action="LOG_ONLY")

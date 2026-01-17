"""Strategy-specific exceptions with severity levels."""


class StrategyException(Exception):
    """Base exception for strategy errors."""
    
    severity: str = "INFO"  # INFO, WARNING, CRITICAL
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ============================================================================
# CRITICAL Exceptions - Must stop strategy immediately
# ============================================================================

class CriticalStrategyException(StrategyException):
    """Critical error that requires immediate strategy shutdown."""
    
    severity = "CRITICAL"


class HedgeFailed(CriticalStrategyException):
    """Hedge order failed - creates single-sided exposure.
    
    This is CRITICAL because:
    - Aster position is already opened
    - Backpack hedge failed
    - Creates directional price risk
    - Must stop immediately to prevent further exposure
    """
    
    def __init__(self, fill_info: dict, error: str):
        message = (
            f"🚨 HEDGE FAILED - SINGLE-SIDED EXPOSURE!\n"
            f"Aster: {fill_info.get('side')} {fill_info.get('qty')} @ {fill_info.get('price')}\n"
            f"Backpack hedge failed: {error}\n"
            f"Strategy MUST stop to prevent further exposure."
        )
        super().__init__(message, details={
            'fill_info': fill_info,
            'error': error,
            'action': 'STOP_STRATEGY',
        })


class InsufficientMarginForHedge(CriticalStrategyException):
    """Insufficient margin on hedge exchange.
    
    This is CRITICAL because:
    - Cannot hedge new positions
    - Will create single-sided exposure
    - Must stop before opening more positions
    """
    
    def __init__(self, exchange: str, required: float, available: float):
        message = (
            f"🚨 INSUFFICIENT MARGIN FOR HEDGING!\n"
            f"Exchange: {exchange}\n"
            f"Required: ${required:.2f}\n"
            f"Available: ${available:.2f}\n"
            f"Cannot hedge new positions - stopping strategy."
        )
        super().__init__(message, details={
            'exchange': exchange,
            'required': required,
            'available': available,
            'action': 'STOP_STRATEGY',
        })


class PositionImbalance(CriticalStrategyException):
    """Position imbalance detected between exchanges.
    
    This is CRITICAL because:
    - Indicates hedge failures or missed fills
    - Creates directional risk
    - Needs immediate attention
    """
    
    def __init__(self, aster_pos: float, backpack_pos: float, threshold: float):
        imbalance = abs(aster_pos + backpack_pos)
        message = (
            f"🚨 POSITION IMBALANCE DETECTED!\n"
            f"Aster: {aster_pos:.4f}\n"
            f"Backpack: {backpack_pos:.4f}\n"
            f"Imbalance: {imbalance:.4f} (threshold: {threshold:.4f})\n"
            f"Stopping strategy for manual review."
        )
        super().__init__(message, details={
            'aster_position': aster_pos,
            'backpack_position': backpack_pos,
            'imbalance': imbalance,
            'threshold': threshold,
            'action': 'STOP_STRATEGY',
        })


# ============================================================================
# WARNING Exceptions - Should log and alert, but can continue
# ============================================================================

class WarningStrategyException(StrategyException):
    """Warning that should be logged and alerted, but strategy can continue."""
    
    severity = "WARNING"


class QuoteOrderFailed(WarningStrategyException):
    """Quote order failed on market making exchange.
    
    This is WARNING because:
    - Reduces market making depth
    - But doesn't create directional risk
    - Strategy can continue with partial quotes
    """
    
    def __init__(self, side: str, amount: float, price: float, error: str):
        message = (
            f"⚠️ Quote order failed\n"
            f"Side: {side}, Amount: {amount:.4f}, Price: {price:.2f}\n"
            f"Error: {error}\n"
            f"Continuing with partial quotes..."
        )
        super().__init__(message, details={
            'side': side,
            'amount': amount,
            'price': price,
            'error': error,
            'action': 'CONTINUE',
        })


class InsufficientMarginForQuotes(WarningStrategyException):
    """Insufficient margin for placing quotes.
    
    This is WARNING because:
    - Cannot place new quotes
    - But existing positions are hedged
    - Can pause quoting and continue monitoring
    """
    
    def __init__(self, exchange: str, required: float, available: float):
        message = (
            f"⚠️ Insufficient margin for quotes\n"
            f"Exchange: {exchange}\n"
            f"Required: ${required:.2f}\n"
            f"Available: ${available:.2f}\n"
            f"Pausing quotes until margin available..."
        )
        super().__init__(message, details={
            'exchange': exchange,
            'required': required,
            'available': available,
            'action': 'PAUSE_QUOTING',
        })


class PriceFeedStale(WarningStrategyException):
    """Price feed data is stale.
    
    This is WARNING because:
    - May lead to bad quotes
    - But can pause quoting until feed recovers
    """
    
    def __init__(self, exchange: str, last_update_seconds: float):
        message = (
            f"⚠️ Price feed stale\n"
            f"Exchange: {exchange}\n"
            f"Last update: {last_update_seconds:.1f}s ago\n"
            f"Pausing quotes until feed recovers..."
        )
        super().__init__(message, details={
            'exchange': exchange,
            'last_update_seconds': last_update_seconds,
            'action': 'PAUSE_QUOTING',
        })


# ============================================================================
# INFO Exceptions - Just for logging, no action needed
# ============================================================================

class InfoStrategyException(StrategyException):
    """Informational exception, no action needed."""
    
    severity = "INFO"


class OrderPartiallyFilled(InfoStrategyException):
    """Order was partially filled."""
    
    def __init__(self, order_id: str, filled: float, total: float):
        message = f"ℹ️ Order {order_id} partially filled: {filled}/{total}"
        super().__init__(message, details={
            'order_id': order_id,
            'filled': filled,
            'total': total,
        })

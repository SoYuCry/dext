"""XAU arbitrage strategy alerts.

This module re-exports the base alert system for convenience.
"""

from strategies.base_alerts import (
    # Re-export alert channels
    AlertChannel,
    TelegramChannel,
    LogChannel,
    # Re-export alert manager
    AlertManager,
    get_alert_manager,
    set_alert_manager,
    # Re-export convenience functions
    send_critical_alert,
    send_warning_alert,
    send_info_alert,
    send_exception_alert,
)

__all__ = [
    # Channels
    "AlertChannel",
    "TelegramChannel",
    "LogChannel",
    # Manager
    "AlertManager",
    "get_alert_manager",
    "set_alert_manager",
    # Convenience functions
    "send_critical_alert",
    "send_warning_alert",
    "send_info_alert",
    "send_exception_alert",
]


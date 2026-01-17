"""Base alert system for trading strategies.

This module provides a unified alerting interface that can send notifications
via multiple channels (Telegram, email, webhooks, etc.) based on severity levels.
"""

import os
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import requests
from logger import setup_logger

logger = setup_logger("strategy.alerts")


# ============================================================================
# Alert Channel Interface
# ============================================================================

class AlertChannel(ABC):
    """Abstract base class for alert channels."""
    
    @abstractmethod
    def send(self, severity: str, title: str, message: str, details: Dict[str, Any]) -> bool:
        """Send alert via this channel.
        
        Args:
            severity: Alert severity (CRITICAL, WARNING, INFO)
            title: Alert title
            message: Alert message
            details: Additional details
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if this channel is enabled."""
        pass


class TelegramChannel(AlertChannel):
    """Telegram alert channel."""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    
    def is_enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)
    
    def send(self, severity: str, title: str, message: str, details: Dict[str, Any]) -> bool:
        if not self.is_enabled():
            return False
        
        try:
            # Format message
            formatted = self._format_message(severity, title, message, details)
            
            # Send via Telegram API
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": formatted,
                "parse_mode": "HTML",
            }
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            
            logger.debug(f"Telegram alert sent: {title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False
    
    def _format_message(self, severity: str, title: str, message: str, details: Dict[str, Any]) -> str:
        """Format message for Telegram."""
        emoji = {
            "CRITICAL": "🚨",
            "WARNING": "⚠️",
            "INFO": "ℹ️",
        }.get(severity, "📢")
        
        lines = [
            f"<b>{emoji} {severity}: {title}</b>",
            "",
            message,
        ]
        
        if details:
            lines.append("")
            lines.append("<b>Details:</b>")
            for key, value in details.items():
                # Skip nested dicts to keep message clean
                if isinstance(value, dict):
                    continue
                lines.append(f"  • {key}: {value}")
        
        return "\n".join(lines)


class LogChannel(AlertChannel):
    """Log-only alert channel (always enabled)."""
    
    def is_enabled(self) -> bool:
        return True
    
    def send(self, severity: str, title: str, message: str, details: Dict[str, Any]) -> bool:
        formatted = f"{severity}: {title}\n{message}"
        
        if severity == "CRITICAL":
            logger.critical(formatted)
        elif severity == "WARNING":
            logger.warning(formatted)
        else:
            logger.info(formatted)
        
        return True


# ============================================================================
# Alert Manager
# ============================================================================

class AlertManager:
    """Manages alerts across multiple channels."""
    
    def __init__(self, channels: Optional[List[AlertChannel]] = None):
        """Initialize alert manager.
        
        Args:
            channels: List of alert channels. If None, uses default channels.
        """
        if channels is None:
            # Default channels: Log + Telegram
            channels = [
                LogChannel(),
                TelegramChannel(),
            ]
        
        self.channels = channels
        self._enabled_channels = [ch for ch in channels if ch.is_enabled()]
        
        logger.info(f"Alert manager initialized with {len(self._enabled_channels)} enabled channels")
    
    def send_critical(self, title: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Send critical alert (highest priority).
        
        Args:
            title: Alert title
            message: Alert message
            details: Additional details
        """
        self._send("CRITICAL", title, message, details or {})
    
    def send_warning(self, title: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Send warning alert.
        
        Args:
            title: Alert title
            message: Alert message
            details: Additional details
        """
        self._send("WARNING", title, message, details or {})
    
    def send_info(self, title: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Send info alert (lowest priority).
        
        Args:
            title: Alert title
            message: Alert message
            details: Additional details
        """
        self._send("INFO", title, message, details or {})
    
    def send_exception(self, exc: Exception) -> None:
        """Send alert for an exception.
        
        Automatically determines severity and formats message based on exception type.
        
        Args:
            exc: Exception to send alert for
        """
        # Check if it's a StrategyException with severity
        if hasattr(exc, 'severity') and hasattr(exc, 'to_dict'):
            exc_dict = exc.to_dict()
            severity = exc_dict['severity']
            title = exc_dict['type']
            message = exc_dict['message']
            details = exc_dict.get('details', {})
            
            self._send(severity, title, message, details)
        else:
            # Generic exception
            self.send_critical(
                title=exc.__class__.__name__,
                message=str(exc),
                details={"type": exc.__class__.__name__}
            )
    
    def _send(self, severity: str, title: str, message: str, details: Dict[str, Any]) -> None:
        """Send alert via all enabled channels.
        
        Args:
            severity: Alert severity
            title: Alert title
            message: Alert message
            details: Additional details
        """
        success_count = 0
        
        for channel in self._enabled_channels:
            try:
                if channel.send(severity, title, message, details):
                    success_count += 1
            except Exception as e:
                logger.error(f"Alert channel {channel.__class__.__name__} failed: {e}")
        
        if success_count == 0:
            logger.error(f"Failed to send alert via any channel: {title}")


# ============================================================================
# Global Alert Manager
# ============================================================================

_global_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create global alert manager instance."""
    global _global_alert_manager
    if _global_alert_manager is None:
        _global_alert_manager = AlertManager()
    return _global_alert_manager


def set_alert_manager(manager: AlertManager) -> None:
    """Set global alert manager instance.
    
    Useful for testing or custom configurations.
    
    Args:
        manager: Alert manager instance to use
    """
    global _global_alert_manager
    _global_alert_manager = manager


# ============================================================================
# Convenience Functions
# ============================================================================

def send_critical_alert(title: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Send critical alert via global alert manager."""
    get_alert_manager().send_critical(title, message, details)


def send_warning_alert(title: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Send warning alert via global alert manager."""
    get_alert_manager().send_warning(title, message, details)


def send_info_alert(title: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Send info alert via global alert manager."""
    get_alert_manager().send_info(title, message, details)


def send_exception_alert(exc: Exception) -> None:
    """Send alert for an exception via global alert manager."""
    get_alert_manager().send_exception(exc)

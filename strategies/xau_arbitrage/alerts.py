"""Alert notification system for strategy events."""
import os
from typing import Optional
import requests
from logger import setup_logger

logger = setup_logger("xau.alerts")


class AlertManager:
    """Manages alerts via Telegram and logging."""
    
    def __init__(self, telegram_bot_token: Optional[str] = None, telegram_chat_id: Optional[str] = None):
        self.telegram_bot_token = telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.telegram_enabled = bool(self.telegram_bot_token and self.telegram_chat_id)
        
        if self.telegram_enabled:
            logger.info("Telegram alerts enabled")
        else:
            logger.warning("Telegram alerts disabled (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
    
    def send_critical(self, title: str, message: str, details: dict = None) -> None:
        """Send critical alert (always via Telegram if enabled)."""
        formatted = self._format_message("🚨 CRITICAL", title, message, details)
        logger.critical(formatted)
        if self.telegram_enabled:
            self._send_telegram(formatted)
    
    def send_warning(self, title: str, message: str, details: dict = None) -> None:
        """Send warning alert (Telegram if enabled)."""
        formatted = self._format_message("⚠️ WARNING", title, message, details)
        logger.warning(formatted)
        if self.telegram_enabled:
            self._send_telegram(formatted)
    
    def send_info(self, title: str, message: str, details: dict = None) -> None:
        """Send info alert (log only, no Telegram)."""
        formatted = self._format_message("ℹ️ INFO", title, message, details)
        logger.info(formatted)
    
    def _format_message(self, level: str, title: str, message: str, details: dict = None) -> str:
        """Format alert message."""
        lines = [
            f"{level}: {title}",
            f"{message}",
        ]
        
        if details:
            lines.append("\nDetails:")
            for key, value in details.items():
                lines.append(f"  {key}: {value}")
        
        return "\n".join(lines)
    
    def _send_telegram(self, message: str) -> None:
        """Send message via Telegram."""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML",
            }
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            logger.debug("Telegram alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create global alert manager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def send_critical_alert(title: str, message: str, details: dict = None) -> None:
    """Send critical alert via global alert manager."""
    get_alert_manager().send_critical(title, message, details)


def send_warning_alert(title: str, message: str, details: dict = None) -> None:
    """Send warning alert via global alert manager."""
    get_alert_manager().send_warning(title, message, details)


def send_info_alert(title: str, message: str, details: dict = None) -> None:
    """Send info alert via global alert manager."""
    get_alert_manager().send_info(title, message, details)

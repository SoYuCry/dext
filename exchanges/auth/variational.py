"""
Variational Exchange Authentication Module

Variational uses cookie-based authentication for API requests.
"""
from typing import Dict, Optional
from exchanges.logger import setup_logger

logger = setup_logger("exchanges.auth.variational")


def create_headers(cookie: str, connected_address: Optional[str] = None) -> Dict[str, str]:
    """
    Create authentication headers for Variational API requests.

    Args:
        cookie: Authentication cookie string
        connected_address: Connected wallet address (optional)

    Returns:
        Dictionary of headers for authenticated requests
    """
    headers = {
        "Cookie": cookie,
        "Content-Type": "application/json",
    }

    if connected_address:
        headers["X-Connected-Address"] = connected_address

    return headers


def validate_cookie(cookie: str) -> bool:
    """
    Validate cookie format.

    Args:
        cookie: Cookie string to validate

    Returns:
        True if cookie appears valid, False otherwise
    """
    if not cookie or not isinstance(cookie, str):
        logger.error("Invalid cookie: empty or not a string")
        return False

    # Basic validation - cookie should contain key-value pairs
    if '=' not in cookie:
        logger.error("Invalid cookie format: no key-value pairs found")
        return False

    return True

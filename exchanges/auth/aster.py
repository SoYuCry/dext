"""
Aster Exchange Authentication Module

Aster uses HMAC-SHA256 signatures for authentication.
"""
import hmac
import hashlib
from typing import Dict, Any
from exchanges.logger import setup_logger

logger = setup_logger("exchanges.auth.aster")


def create_signature(secret_key: str, query_string: str) -> str:
    """
    Create HMAC-SHA256 signature for Aster API requests.

    Args:
        secret_key: API secret key
        query_string: Query string to sign

    Returns:
        Hexadecimal signature string
    """
    return hmac.new(
        secret_key.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def sign_request(params: Dict[str, Any], secret_key: str) -> str:
    """
    Sign request parameters for Aster API.

    Args:
        params: Request parameters dictionary
        secret_key: API secret key

    Returns:
        HMAC-SHA256 signature
    """
    # Sort parameters alphabetically and create query string
    sorted_params = sorted(params.items())
    query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
    return create_signature(secret_key, query_string)

"""Binance authentication helpers.

Binance uses HMAC SHA256 signature for authentication.
API Documentation: https://binance-docs.github.io/apidocs/spot/en/#signed-trade-and-user_data-endpoint-security
"""
import hmac
import hashlib
from typing import Dict, Any
from urllib.parse import urlencode


def create_signature(secret_key: str, query_string: str) -> str:
    """Create HMAC SHA256 signature for Binance API.

    Args:
        secret_key: API secret key
        query_string: Query string to sign (already URL-encoded)

    Returns:
        Hex-encoded signature string

    Example:
        >>> secret = "my_secret_key"
        >>> query = "symbol=BTCUSDT&side=BUY&type=LIMIT&quantity=1&timestamp=1234567890"
        >>> sig = create_signature(secret, query)
        >>> # sig = "c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71"
    """
    return hmac.new(
        secret_key.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def sign_request(secret_key: str, params: Dict[str, Any]) -> str:
    """Sign request parameters for Binance API.

    Args:
        secret_key: API secret key
        params: Request parameters (dict)

    Returns:
        Signature string to append to request

    Example:
        >>> params = {"symbol": "BTCUSDT", "side": "BUY", "timestamp": 1234567890}
        >>> sig = sign_request("my_secret", params)
    """
    # Sort parameters and create query string
    query_string = urlencode(sorted(params.items()))

    # Create signature
    signature = create_signature(secret_key, query_string)

    return signature

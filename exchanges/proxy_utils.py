"""
Proxy configuration utility module
Reads proxy settings from environment variables for use by all API clients
"""
import os
from typing import Dict
from exchanges.logger import setup_logger

logger = setup_logger("exchanges.proxy_utils")


def get_proxy_config() -> Dict[str, str]:
    """
    Read proxy configuration from environment variables

    Priority:
    1. If HTTPS_PROXY is set, use it for HTTPS
    2. If only HTTP_PROXY is set, use it for both HTTP and HTTPS
    3. If neither is set, return an empty dict

    Returns:
        Dict[str, str]: Proxy configuration dict, e.g. {'http': '...', 'https': '...'}
    """
    http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
    https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')

    proxies = {}

    if http_proxy:
        proxies['http'] = http_proxy
        # If https_proxy is not explicitly set, use http_proxy for HTTPS as well
        if not https_proxy:
            proxies['https'] = http_proxy

    if https_proxy:
        proxies['https'] = https_proxy

    if proxies:
        logger.info(f"Proxy config loaded from environment: HTTP={'http' in proxies}, HTTPS={'https' in proxies}")
        logger.debug(f"Proxy config details: {proxies}")
    else:
        logger.debug("No proxy configuration detected")

    return proxies

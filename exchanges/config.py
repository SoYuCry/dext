"""Minimal configuration for exchange clients."""
import os
from dotenv import load_dotenv

# Python 3.13: load_dotenv() without explicit path may assert in some contexts.
load_dotenv(dotenv_path=".env")

# Global proxy config
HTTP_PROXY = os.getenv("HTTP_PROXY")
HTTPS_PROXY = os.getenv("HTTPS_PROXY")

# Logging
LOG_FILE = os.getenv("LOG_FILE", "market_maker.log")

# Backpack
BACKPACK_API_KEY = os.getenv("BACKPACK_KEY") or os.getenv("API_KEY")
BACKPACK_SECRET_KEY = os.getenv("BACKPACK_SECRET") or os.getenv("SECRET_KEY")
BACKPACK_API_URL = os.getenv("BACKPACK_API_URL", "https://api.backpack.exchange")
BACKPACK_WS_URL = os.getenv("BACKPACK_WS_URL", "wss://ws.backpack.exchange")
BACKPACK_API_VERSION = os.getenv("BACKPACK_API_VERSION", "v1")
BACKPACK_DEFAULT_WINDOW = os.getenv("BACKPACK_DEFAULT_WINDOW", "5000")

# Aster
ASTER_API_KEY = os.getenv("ASTER_API_KEY") or os.getenv("ASTER_KEY")
ASTER_SECRET_KEY = os.getenv("ASTER_SECRET_KEY") or os.getenv("ASTER_SECRET")
ASTER_BASE_URL = os.getenv("ASTER_BASE_URL", "https://api.aster.exchange")

# Binance
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY") or os.getenv("BINANCE_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY") or os.getenv("BINANCE_SECRET")
BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")
BINANCE_WS_URL = os.getenv("BINANCE_WS_URL", "wss://stream.binance.com:9443")

# Lighter
LIGHTER_PRIVATE_KEY = os.getenv("LIGHTER_PRIVATE_KEY") or os.getenv("LIGHTER_API_KEY")
LIGHTER_ACCOUNT_INDEX = os.getenv("LIGHTER_ACCOUNT_INDEX")
LIGHTER_API_KEY_INDEX = os.getenv("LIGHTER_API_KEY_INDEX")
LIGHTER_BASE_URL = os.getenv("LIGHTER_BASE_URL")

# Variational / Omni
VARIATIONAL_COOKIE = os.getenv("VARIATIONAL_COOKIE") or os.getenv("VR_COOKIE")
VARIATIONAL_CONNECTED_ADDRESS = os.getenv("VARIATIONAL_CONNECTED_ADDRESS") or os.getenv("VR_CONNECTED_ADDRESS")
VARIATIONAL_COUNTERPARTY_ID = os.getenv("VARIATIONAL_COUNTERPARTY_ID") or os.getenv("VR_COUNTERPARTY_ID")
VARIATIONAL_BASE_URL = os.getenv("VARIATIONAL_BASE_URL", "https://omni.variational.io/api")
VARIATIONAL_API_VERSION = os.getenv("VARIATIONAL_API_VERSION", "v2")
VARIATIONAL_IMPERSONATE = os.getenv("VARIATIONAL_IMPERSONATE", "chrome120")
VARIATIONAL_WS_URL = os.getenv(
    "VARIATIONAL_WS_URL",
    "wss://omni-ws-server.prod.ap-northeast-1.variational.io/events",
)
VARIATIONAL_WS_AUTH = os.getenv("VARIATIONAL_WS_AUTH")
VARIATIONAL_WS_QUERY = os.getenv("VARIATIONAL_WS_QUERY")
VARIATIONAL_WS_CLAIMS = os.getenv("VARIATIONAL_WS_CLAIMS")

# Backward-compatible aliases (keep for legacy imports)
API_KEY = BACKPACK_API_KEY
SECRET_KEY = BACKPACK_SECRET_KEY
API_URL = BACKPACK_API_URL
WS_URL = BACKPACK_WS_URL
API_VERSION = BACKPACK_API_VERSION
DEFAULT_WINDOW = BACKPACK_DEFAULT_WINDOW

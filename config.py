"""Minimal configuration for ccxt-style exchange clients."""
import os
from dotenv import load_dotenv

load_dotenv()

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

# Lighter
LIGHTER_PRIVATE_KEY = os.getenv("LIGHTER_PRIVATE_KEY") or os.getenv("LIGHTER_API_KEY")
LIGHTER_ACCOUNT_INDEX = os.getenv("LIGHTER_ACCOUNT_INDEX")
LIGHTER_API_KEY_INDEX = os.getenv("LIGHTER_API_KEY_INDEX")
LIGHTER_BASE_URL = os.getenv("LIGHTER_BASE_URL")

# Backward-compatible aliases (keep for legacy imports)
API_KEY = BACKPACK_API_KEY
SECRET_KEY = BACKPACK_SECRET_KEY
API_URL = BACKPACK_API_URL
WS_URL = BACKPACK_WS_URL
API_VERSION = BACKPACK_API_VERSION
DEFAULT_WINDOW = BACKPACK_DEFAULT_WINDOW

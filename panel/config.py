"""Panel configuration - load from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

# Exchange API credentials
ASTER_API_KEY = os.getenv("ASTER_API_KEY") or os.getenv("ASTER_KEY")
ASTER_SECRET = os.getenv("ASTER_SECRET_KEY") or os.getenv("ASTER_SECRET")

BACKPACK_API_KEY = os.getenv("BACKPACK_KEY") or os.getenv("BACKPACK_API_KEY")
BACKPACK_SECRET = os.getenv("BACKPACK_SECRET") or os.getenv("BACKPACK_SECRET_KEY")

# Trading symbols
ASTER_SYMBOL = os.getenv("ASTER_SYMBOL", "XAUUSDT")
BACKPACK_SYMBOL = os.getenv("BACKPACK_SYMBOL", "PAXG_USDC_PERP")

# Server configuration
HOST = os.getenv("PANEL_HOST", "127.0.0.1")
PORT = int(os.getenv("PANEL_PORT", "8765"))

# Update intervals
POSITION_UPDATE_INTERVAL = float(os.getenv("POSITION_UPDATE_INTERVAL", "5.0"))  # seconds
ORDER_UPDATE_INTERVAL = float(os.getenv("ORDER_UPDATE_INTERVAL", "3.0"))  # seconds

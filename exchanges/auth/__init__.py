"""
Authentication modules for different exchanges.

This package contains exchange-specific authentication implementations:
- backpack: Ed25519 signature authentication
- lighter: zkSync native signer authentication
- aster: HMAC-SHA256 signature authentication
- variational: Cookie-based authentication
"""

from . import backpack
from . import lighter
from . import aster
from . import variational

__all__ = [
    "backpack",
    "lighter",
    "aster",
    "variational",
]

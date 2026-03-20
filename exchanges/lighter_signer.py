"""Legacy import path for Lighter native signer.

Prefer `exchanges.auth.lighter` going forward.
"""
from exchanges.auth.lighter import SimpleSignerClient, SimpleSignerError

__all__ = ["SimpleSignerClient", "SimpleSignerError"]

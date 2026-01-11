"""Compatibility alias for the Backpack exchange client."""

from .exchanges import Backpack

# Preserve legacy name
BPClient = Backpack

__all__ = ["BPClient", "Backpack"]

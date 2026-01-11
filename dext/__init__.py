"""
`dext` is a lightweight wrapper package to make this repo easy to `pip install -e`
and import from strategy projects.
"""

from api import get_client as get_client

__all__ = ["get_client"]


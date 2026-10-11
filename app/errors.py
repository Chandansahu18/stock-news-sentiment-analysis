"""Errors the service layer raises and the API layer turns into HTTP responses.

Messages are written for end users: they never contain tokens, URLs with secrets or stack traces.
"""

from __future__ import annotations


class UnknownSymbolError(Exception):
    """The symbol is not a listed NSE equity (HTTP 404)."""


class DataUnavailableError(Exception):
    """Needed data could not be fetched or is not configured (HTTP 503)."""

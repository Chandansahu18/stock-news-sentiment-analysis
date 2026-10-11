"""The price block: range selector, quote summary and candlestick chart."""

from __future__ import annotations

import streamlit as st

from ui import charts, components
from ui.api_client import ApiError, stock_path

RANGES = {"1 month": 30, "3 months": 90, "6 months": 180}
DEFAULT_RANGE = "1 month"


def render_controls() -> int:
    """Draw the range selector and return the chosen number of days."""
    chosen = st.segmented_control("Price history", list(RANGES), default=DEFAULT_RANGE) or DEFAULT_RANGE
    return RANGES[chosen]


def api_call(symbol: str, days: int) -> tuple[str, dict]:
    return stock_path(symbol, "prices"), {"days": days}


def render(slot, stock: dict, result) -> None:
    """Fill `slot` with the prices, or with a notice if `result` is an ApiError."""
    if isinstance(result, ApiError):
        slot.html(components.notice("Price is not available right now", str(result)))
        return
    with slot.container():
        if result.get("stale"):
            st.html(components.notice("Showing the last prices we saved", f'We could not get fresh prices just now. {result.get("warning", "")}'.strip()))
        st.html(components.price_summary(stock, result))
        st.plotly_chart(charts.candlestick(result["candles"]), width="stretch", config={"displayModeBar": False})

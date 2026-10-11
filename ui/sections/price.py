"""The price block: range selector, quote summary and candlestick chart."""

from __future__ import annotations

import streamlit as st

from ui import charts, components
from ui.api_client import ApiError, stock_path

RANGES = {"1M": 30, "3M": 90, "6M": 180}


def render_controls() -> int:
    """Draw the range selector and return the chosen number of days."""
    chosen = st.segmented_control("Price range", list(RANGES), default="1M") or "1M"
    return RANGES[chosen]


def api_call(symbol: str, days: int) -> tuple[str, dict]:
    return stock_path(symbol, "prices"), {"days": days}


def render(slot, stock: dict, result) -> None:
    """Fill `slot` with the prices, or with a notice if `result` is an ApiError."""
    if isinstance(result, ApiError):
        slot.html(components.notice("Price data is unavailable", str(result)))
        return
    with slot.container():
        if result.get("stale"):
            st.html(components.notice("Showing older prices", f'Refreshing failed: {result.get("warning", "unknown error")}'))
        st.html(components.price_summary(stock, result))
        st.plotly_chart(charts.candlestick(result["candles"]), width="stretch", config={"displayModeBar": False})

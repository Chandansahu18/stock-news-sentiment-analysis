"""The "Today's stocks" selector, its explanatory notes and the row of ranked stocks to pick from."""

from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

from ui import components
from ui.api_client import ApiError, get_cached
from ui.formatting import IST
from . import selection


def render() -> list[dict] | None:
    """Draw the section and return the ranked stocks, or None if the page cannot continue."""
    mode = (
        st.segmented_control(
            "Today's stocks",
            list(components.MODE_LABELS),
            default="active",
            format_func=components.MODE_LABELS.get,
            key="top_mode",
        )
        or "active"
    )
    try:
        top = get_cached("/stocks/top", mode=mode)
    except ApiError as error:
        st.html(components.notice("Today's stocks are unavailable", str(error), "error"))
        return None

    if top["fallback"]:
        st.html(components.notice("Showing the default watchlist", top.get("warning") or "Live rankings are unavailable."))
    elif top["stale"]:
        st.html(components.notice("Showing the last saved ranking", f'Refreshing failed: {top.get("warning", "unknown error")}'))
    caption = components.top_stocks_caption(top, datetime.now(IST).date().isoformat())
    if caption:
        st.html(f'<p class="pv-meta">{escape(caption)}</p>')

    ranked = top["stocks"]
    if not ranked and selection.selected_symbol() is None:
        st.html(components.notice("Nothing to show yet", "No stocks matched this ranking today. Try another list or search above."))
        return None
    selection.select_first_if_nothing_selected(ranked)

    labels = {stock["symbol"]: components.stock_pill_label(stock) for stock in ranked}
    if labels:
        chosen = selection.selected_symbol()
        st.session_state[selection.TOP_PICK_KEY] = chosen if chosen in labels else None
        st.pills("Pick a stock", list(labels), key=selection.TOP_PICK_KEY, format_func=labels.get, on_change=selection.pick_from_top)
    return ranked

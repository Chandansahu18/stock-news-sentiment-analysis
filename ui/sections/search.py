"""The search box, the "Refresh news" button and the list of matching stocks."""

from __future__ import annotations

import streamlit as st

from ui import components
from ui.api_client import ApiError, get_cached
from . import selection

MAX_QUERY_LENGTH = 40
MAX_MATCHES = 8


def render() -> bool:
    """Draw the search row. Returns True if "Refresh news" was pressed in this run."""
    search_column, refresh_column = st.columns([5, 1.4], vertical_alignment="bottom")
    query = search_column.text_input(
        "Search stocks",
        key="search_query",
        placeholder="Company name or symbol, for example Infosys or HDFCBANK",
        max_chars=MAX_QUERY_LENGTH,
    ).strip()
    refresh_requested = refresh_column.button(
        "Refresh news", icon=":material/refresh:", width="stretch", help="Re-fetch and re-score news, ignoring the cache"
    )
    if query:
        _render_matches(query)
    return refresh_requested


def _render_matches(query: str) -> None:
    try:
        matches = get_cached("/stocks/search", q=query, limit=MAX_MATCHES)
    except ApiError as error:
        st.html(components.notice("Search is unavailable", str(error), "error"))
        return
    if not matches:
        st.html(components.notice(f'No NSE stock matches "{query}"', "Check the spelling, or try the symbol, for example TCS."))
        return
    names = {stock["symbol"]: stock["name"] for stock in matches}
    chosen = selection.selected_symbol()
    st.session_state[selection.SEARCH_PICK_KEY] = chosen if chosen in names else None
    st.pills(
        "Search results",
        list(names),
        key=selection.SEARCH_PICK_KEY,
        format_func=lambda symbol: f"{symbol}  {names[symbol]}",
        on_change=selection.pick_from_search,
    )

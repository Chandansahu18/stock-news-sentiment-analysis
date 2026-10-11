"""Which stock is selected. The choice survives Streamlit re-runs in the browser session's state."""

from __future__ import annotations

import streamlit as st

from ui.api_client import ApiError, get_cached

SELECTED_SYMBOL_KEY = "selected_symbol"
SEARCH_PICK_KEY = "search_pick"   # the "Search results" pills
TOP_PICK_KEY = "top_pick"         # the "Pick a stock" pills


def selected_symbol() -> str | None:
    return st.session_state.get(SELECTED_SYMBOL_KEY)


def pick_from_search() -> None:
    """Callback for the search-result pills. Only one set of pills shows the selection at a time."""
    if st.session_state.get(SEARCH_PICK_KEY):
        st.session_state[SELECTED_SYMBOL_KEY] = st.session_state[SEARCH_PICK_KEY]
        st.session_state[TOP_PICK_KEY] = None


def pick_from_top() -> None:
    """Callback for the ranked-stock pills."""
    if st.session_state.get(TOP_PICK_KEY):
        st.session_state[SELECTED_SYMBOL_KEY] = st.session_state[TOP_PICK_KEY]
        st.session_state[SEARCH_PICK_KEY] = None


def select_first_if_nothing_selected(ranked_stocks: list[dict]) -> None:
    if selected_symbol() is None and ranked_stocks:
        st.session_state[SELECTED_SYMBOL_KEY] = ranked_stocks[0]["symbol"]


def resolve_selected_stock(ranked_stocks: list[dict]) -> dict:
    """{"symbol", "name"} of the selected stock. The name comes from the ranking, or from search if it is not ranked."""
    symbol = selected_symbol()
    name = next((s["name"] for s in ranked_stocks if s["symbol"] == symbol), None)
    if name is None:
        try:
            name = get_cached("/stocks/search", q=symbol, limit=1)[0]["name"]
        except (ApiError, IndexError):
            name = symbol
    return {"symbol": symbol, "name": name}

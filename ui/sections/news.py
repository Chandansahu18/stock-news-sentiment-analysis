"""The news block: period selector, sentiment summary, filter tabs and the article list."""

from __future__ import annotations

from html import escape

import streamlit as st

from ui import components
from ui.api_client import ApiError, call_api, clear_cache, get_cached, stock_path
from ui.formatting import format_timestamp
from ui.theme import SENTIMENT_LABELS, SENTIMENT_ORDER

WINDOWS = {"Today": 1, "3 days": 3, "7 days": 7}
WIDEST_WINDOW_DAYS = max(WINDOWS.values())
FILTERS = ("all", *SENTIMENT_ORDER)


def render_heading() -> None:
    st.html('<h2 class="pv-h2">News sentiment</h2>')


def render_controls() -> str:
    """Draw the period selector and return its label ("Today", "3 days" or "7 days")."""
    return st.segmented_control("News from", list(WINDOWS), default="Today", key="news_window") or "Today"


def api_call(symbol: str, window_label: str) -> tuple[str, dict]:
    return stock_path(symbol, "news"), {"days": WINDOWS[window_label]}


def refresh(symbol: str) -> None:
    """Ask the backend to re-fetch this stock's news, then forget what the dashboard remembered."""
    try:
        call_api("POST", stock_path(symbol, "refresh"))
        clear_cache()
    except ApiError as error:
        st.toast(f"Refresh failed: {error}", icon=":material/error:")


def _widen_if_empty(symbol: str, window_label: str, news: dict) -> tuple[dict, bool]:
    """If nothing was published in the chosen period, fall back to the past week. Returns (news, was_widened)."""
    if news["articles"] or WINDOWS[window_label] >= WIDEST_WINDOW_DAYS:
        return news, False
    try:
        wider = get_cached(stock_path(symbol, "news"), days=WIDEST_WINDOW_DAYS)  # answered from the backend's cache
    except ApiError:
        return news, False
    return (wider, True) if wider["articles"] else (news, False)


def render(slot, stock: dict, result, window_label: str) -> None:
    """Fill `slot` with the news, or with a notice if `result` is an ApiError."""
    if isinstance(result, ApiError):
        slot.html(components.notice("News could not be loaded", str(result), "error"))
        return
    news, widened = _widen_if_empty(stock["symbol"], window_label, result)
    articles = news["articles"]
    with slot.container():
        if news.get("stale"):
            st.html(components.notice("Showing saved results", f'Refreshing failed: {news.get("warning", "unknown error")}'))
        if widened:
            st.html(components.notice("No articles for the selected period", f'Nothing was published for "{window_label}". Showing the past 7 days instead.'))
        if not articles:
            st.html(components.notice(f'No recent news for {stock["name"]}', "Nothing was published in the last week, or the news source returned no matches. Try Refresh news later."))
            return
        st.html(components.sentiment_summary(news["summary"]))
        _render_articles(news, articles)


def _render_articles(news: dict, articles: list[dict]) -> None:
    counts = news["summary"]["counts"]
    tab_labels = {"all": f"All {len(articles)}", **{label: f"{SENTIMENT_LABELS[label]} {counts.get(label, 0)}" for label in SENTIMENT_ORDER}}
    chosen = st.segmented_control("Show", FILTERS, default="all", format_func=tab_labels.get) or "all"
    shown = articles if chosen == "all" else [a for a in articles if a["sentiment"]["label"] == chosen]
    if shown:
        st.html(components.article_list(shown))
    else:
        st.html(components.notice(f"No {chosen} articles", "Pick another filter to see the rest."))
    origin = "saved copy" if news.get("from_cache") else "just fetched"
    st.html(f'<p class="pv-meta">Source: {escape(news["source"].title())}. Updated {escape(format_timestamp(news["fetched_at"]))} ({origin}).</p>')

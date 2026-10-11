"""The news block: period selector, sentiment summary, filter tabs and the article list."""

from __future__ import annotations

from html import escape

import streamlit as st

from ui import components
from ui.api_client import ApiError, call_api, clear_cache, get_cached, stock_path
from ui.formatting import format_timestamp
from ui.theme import SENTIMENT_LABELS, SENTIMENT_ORDER

WINDOWS = {"Today": 1, "Last 3 days": 3, "Last 7 days": 7}
WIDEST_WINDOW_DAYS = max(WINDOWS.values())
FILTERS = ("all", *SENTIMENT_ORDER)


def render_heading() -> None:
    st.html('<h2 class="pv-h2">What the news is saying</h2>')


def render_controls() -> str:
    """Draw the period selector and return its label ("Today", "Last 3 days" or "Last 7 days")."""
    return st.segmented_control("News from", list(WINDOWS), default="Today", key="news_window") or "Today"


def api_call(symbol: str, window_label: str) -> tuple[str, dict]:
    return stock_path(symbol, "news"), {"days": WINDOWS[window_label]}


def refresh(symbol: str) -> None:
    """Ask the backend to re-fetch this stock's news, then forget what the dashboard remembered."""
    try:
        call_api("POST", stock_path(symbol, "refresh"))
        clear_cache()
    except ApiError as error:
        st.toast(f"We could not refresh the news: {error}", icon=":material/error:")


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
        slot.html(components.notice("We could not load the news", str(result), "error"))
        return
    news, widened = _widen_if_empty(stock["symbol"], window_label, result)
    articles = news["articles"]
    with slot.container():
        if news.get("stale"):
            st.html(components.notice("Showing news we saved earlier", f'We could not check for new headlines just now. {news.get("warning", "")}'.strip()))
        if widened:
            st.html(components.notice("No news for the time you picked", f'We found nothing for "{window_label}", so here is the past week instead.'))
        if not articles:
            st.html(components.notice(f'No recent news for {stock["name"]}', "We found nothing from the past week. Try Get latest news again a little later."))
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
        st.html(components.notice(f"No {chosen} news in this list", "Pick another filter to see the rest."))
    st.html(f'<p class="pv-meta">News from {escape(news["source"].title())}. Last updated {escape(format_timestamp(news["fetched_at"]))}.</p>')

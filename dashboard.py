"""Streamlit dashboard. It talks to the FastAPI backend only, never to Upstox or Google directly.

Run:  streamlit run dashboard.py

The page is assembled from the blocks in ui/sections. The price and the news are requested at the same
time, with loading placeholders already on screen, so the wait is the slower of the two, not the sum.
"""

import streamlit as st

from ui import components, theme
from ui.api_client import fetch_concurrently
from ui.sections import news, page_frame, price, search, selection, top_stocks

st.set_page_config(page_title="Stock news sentiment", page_icon=":material/monitoring:", layout="wide")
st.html(f"<style>{theme.stylesheet()}</style>")

page_frame.render_header()
refresh_requested = search.render()

ranked_stocks = top_stocks.render()
if ranked_stocks is None:
    st.stop()
stock = selection.resolve_selected_stock(ranked_stocks)

# Lay out the whole page first, with placeholders where the data will appear...
price_days = price.render_controls()
price_slot = st.empty()
price_slot.html(components.loading_placeholder("quote"))
news.render_heading()
news_window = news.render_controls()
news_slot = st.empty()
news_slot.html(components.loading_placeholder("news"))

# ...then fetch both at once and fill the placeholders.
if refresh_requested:
    news.refresh(stock["symbol"])
results = fetch_concurrently(
    {
        "prices": price.api_call(stock["symbol"], price_days),
        "news": news.api_call(stock["symbol"], news_window),
    }
)
price.render(price_slot, stock, results["prices"])
news.render(news_slot, stock, results["news"], news_window)

page_frame.render_footer()

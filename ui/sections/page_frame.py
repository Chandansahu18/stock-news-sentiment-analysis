"""Page title and footer."""

from __future__ import annotations

import streamlit as st

PAGE_TITLE = "Stocks News Mood"


def render_header() -> None:
    st.html(
        f'<h1 class="pv-h1">{PAGE_TITLE}</h1>'
        '<p class="pv-lede">India\'s busiest stocks, the news behind them, and whether the headlines are positive or negative, '
        "right next to the price.</p>"
    )


def render_footer() -> None:
    st.html(
        '<p class="pv-foot">For information only, not investment advice. The positive, neutral and negative ratings come '
        "from an automatic reading of headlines, so they can sometimes be wrong.</p>"
    )

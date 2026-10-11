"""Page title and footer."""

from __future__ import annotations

import streamlit as st


def render_header() -> None:
    st.html(
        '<h1 class="pv-h1">Stock news sentiment</h1>'
        '<p class="pv-lede">Today\'s most talked-about NSE stocks, with headlines scored by FinBERT next to the price.</p>'
    )


def render_footer() -> None:
    st.html(
        '<p class="pv-foot">For information only, not investment advice. Scores are model estimates '
        "from headlines and can be wrong.</p>"
    )

"""Plotly chart styling. Transparent background so Streamlit's light/dark theme shows through."""

from __future__ import annotations

import plotly.graph_objects as go

from .theme import NEGATIVE, POSITIVE

_GRID_COLOR = "rgba(128,128,128,0.18)"


def candlestick(candles: list[dict]) -> go.Figure:
    """Daily candles. Up days are hollow, down days are filled, so direction is not colour-only."""
    figure = go.Figure(
        go.Candlestick(
            x=[c["date"] for c in candles],
            open=[c["open"] for c in candles],
            high=[c["high"] for c in candles],
            low=[c["low"] for c in candles],
            close=[c["close"] for c in candles],
            increasing=dict(line=dict(color=POSITIVE, width=1.5), fillcolor="rgba(0,0,0,0)"),
            decreasing=dict(line=dict(color=NEGATIVE, width=1.5), fillcolor=NEGATIVE),
            whiskerwidth=0.4,
            name="Price",
        )
    )
    figure.update_layout(
        height=340,
        margin=dict(l=0, r=0, t=8, b=0),
        showlegend=False,
        hovermode="x unified",
        xaxis=dict(
            rangeslider=dict(visible=False),
            gridcolor=_GRID_COLOR,
            rangebreaks=[dict(bounds=["sat", "mon"])],  # no empty weekend gaps
        ),
        yaxis=dict(tickprefix="₹", tickformat=",.0f", gridcolor=_GRID_COLOR, zeroline=False, side="right"),
    )
    return figure

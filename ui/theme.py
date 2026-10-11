"""Colours and styles. Kept free of Streamlit so the tests can check the real values for contrast.

The semantic colours are used for shapes (needs 3:1 contrast) and, mixed with the theme's text colour,
for text (needs 4.5:1). tests/test_ui_theme.py checks both against the real light and dark themes.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

POSITIVE = "#2a9461"
NEGATIVE = "#d4483b"
NEUTRAL = "#80858e"
TEXT_MIX_PERCENT = 55  # how much of a semantic colour is mixed into the current text colour

SENTIMENT_LABELS = {"positive": "Positive", "neutral": "Neutral", "negative": "Negative"}
SENTIMENT_ORDER = ("positive", "neutral", "negative")

STYLESHEET_PATH = Path(__file__).parent / "styles.css"


def color_variables() -> str:
    return f":root{{--pv-pos:{POSITIVE};--pv-neg:{NEGATIVE};--pv-neu:{NEUTRAL};--pv-mix:{TEXT_MIX_PERCENT}%;}}"


@lru_cache(maxsize=1)
def stylesheet() -> str:
    """Colour variables plus styles.css. Read from disk once, not on every Streamlit re-run."""
    return f"{color_variables()}\n{STYLESHEET_PATH.read_text(encoding='utf-8')}"

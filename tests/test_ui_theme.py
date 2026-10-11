import re
import tomllib
from pathlib import Path

import pytest

from ui import theme

ROOT = Path(__file__).resolve().parent.parent
THEME = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["theme"]


# ---------- accessibility of the real theme (WCAG AA) ----------

def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    linear = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)


def contrast(a: str, b: str) -> float:
    lighter, darker = sorted((luminance(a), luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def mix(semantic: str, text: str, percent: int) -> str:
    """CSS color-mix(in srgb, semantic <percent>%, text)."""
    s = [int(semantic.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    t = [int(text.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(percent / 100 * a + (1 - percent / 100) * b):02x}" for a, b in zip(s, t))


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_theme_contrast(mode):
    colors = THEME[mode]
    background, surface, text = colors["backgroundColor"], colors["secondaryBackgroundColor"], colors["textColor"]
    assert contrast(text, background) >= 7 and contrast(text, surface) >= 7
    assert contrast("#ffffff", colors["primaryColor"]) >= 4.5   # white label on primary buttons
    assert contrast(colors["primaryColor"], background) >= 3    # focus ring and selected outline
    # semantic shapes (triangles, bars) are graphics: they need 3:1
    for color in (theme.POSITIVE, theme.NEGATIVE, theme.NEUTRAL):
        assert contrast(color, background) >= 3, (mode, color)
    # semantic text is the semantic colour mixed into the text colour: it needs 4.5:1
    for color in (theme.POSITIVE, theme.NEGATIVE):
        mixed = mix(color, text, theme.TEXT_MIX_PERCENT)
        assert contrast(mixed, background) >= 4.5, (mode, color, mixed)


def test_link_colour_is_readable_in_dark_mode():
    assert contrast(THEME["dark"]["linkColor"], THEME["dark"]["backgroundColor"]) >= 4.5


def test_no_pure_black_or_white_in_the_theme():
    flat = str(THEME).lower()
    assert "#000000" not in flat and "#ffffff" not in flat


# ---------- house style: no em or en dashes in anything the user can read ----------

USER_FACING_FILES = sorted(
    [p.relative_to(ROOT).as_posix() for p in ROOT.glob("ui/**/*.py")] + ["dashboard.py", "ui/styles.css"]
)


@pytest.mark.parametrize("path", USER_FACING_FILES)
def test_no_em_or_en_dashes(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    assert not re.search("[\u2014\u2013]", text), f"{path} contains an em or en dash"


# ---------- the stylesheet ----------

def test_stylesheet_defines_the_colour_variables_and_is_read_once():
    css = theme.stylesheet()
    assert f"--pv-pos:{theme.POSITIVE}" in css and ".pv-row" in css
    assert theme.stylesheet() is css  # cached: not re-read from disk on every Streamlit re-run

import pytest

from ui import components
from ui.formatting import format_day, format_rupees, format_signed, format_timestamp


# ---------- formatting ----------

@pytest.mark.parametrize(
    "amount,expected",
    [(2156.0, "₹2,156.00"), (123456.5, "₹1,23,456.50"), (12345678.9, "₹1,23,45,678.90"), (999.5, "₹999.50"), (-7.7, "-₹7.70")],
)
def test_rupees_use_indian_digit_grouping(amount, expected):
    assert format_rupees(amount) == expected


def test_signed_numbers_and_timestamps():
    assert format_signed(80.0) == "+80.00" and format_signed(-7.7) == "-7.70" and format_signed(0.0) == "0.00"
    assert format_timestamp("2026-10-09T12:00:00+00:00") == "09 Oct, 5:30 PM IST"
    assert format_timestamp("not a date") == "not a date"


def test_format_day():
    assert format_day("2026-10-09") == "09 Oct" and format_day(None) == "" and format_day("junk") == ""


# ---------- safety: article text and URLs come from third parties ----------

def make_item(**overrides):
    base = {
        "title": "TCS wins deal", "summary": "", "url": "https://example.com/a", "source": "Mint",
        "published_at": "2026-10-09T10:00:00+00:00",
        "sentiment": {"label": "positive", "score": 0.91, "compound": 0.8, "probs": {"positive": 0.9, "neutral": 0.05, "negative": 0.05}},
    }
    return {**base, **overrides}


def test_article_escapes_html_in_every_field():
    html = components.article_row(make_item(title='<img src=x onerror="alert(1)">', summary="<script>alert(1)</script>", source="<b>Evil</b>"))
    assert "<img" not in html and "<script" not in html and "<b>" not in html
    assert "&lt;img" in html and "&lt;script&gt;" in html


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,<script>1</script>", "//evil.example", "ftp://x.y/z", "", None, "https://"])
def test_unsafe_urls_are_not_linked(url):
    assert components.safe_link_url(url) == ""
    html = components.article_row(make_item(url=url))
    assert "<a " not in html and "href" not in html


def test_safe_links_open_in_a_new_tab_without_opener_access():
    html = components.article_row(make_item(url='https://example.com/a?x="1"&y=2'))
    assert 'target="_blank"' in html and 'rel="noopener noreferrer"' in html
    assert "x=&quot;1&quot;" in html  # the attribute value is quoted safely


def test_article_shows_label_text_and_confidence_not_just_colour():
    html = components.article_row(make_item())
    assert "Positive" in html and "91% sure" in html and 'aria-hidden="true"' in html


# ---------- components ----------

def test_sentiment_summary_has_a_text_alternative():
    summary = {"overall": "positive", "average_score": 0.29, "article_count": 6, "counts": {"positive": 4, "neutral": 1, "negative": 1}}
    html = components.sentiment_summary(summary)
    assert 'aria-label="4 positive, 1 neutral, 1 negative"' in html
    assert "Positive" in html and "Based on 6 headlines" in html and "flex:4" in html and "4 positive" in html


def test_sentiment_summary_speaks_plainly_without_scores_or_jargon():
    summary = {"overall": "negative", "average_score": -0.4, "article_count": 3, "counts": {"positive": 0, "neutral": 1, "negative": 2}}
    html = components.sentiment_summary(summary)
    assert "Negative" in html
    for jargon in ("-0.40", "scale", "Average score", "confidence"):
        assert jargon not in html


def test_sentiment_summary_uses_the_singular_for_one_headline():
    summary = {"overall": "neutral", "average_score": -0.12, "article_count": 1, "counts": {"positive": 0, "neutral": 1, "negative": 0}}
    assert "Based on 1 headline<" in components.sentiment_summary(summary)


def test_empty_sentiment_summary_renders_nothing():
    empty = {"overall": "neutral", "average_score": 0, "article_count": 0, "counts": {"positive": 0, "neutral": 0, "negative": 0}}
    assert components.sentiment_summary(empty) == ""


def test_price_summary_shows_signs_and_period_range():
    prices = {
        "price": 2156.0, "previous_close": 2076.0, "change": 80.0, "change_pct": 3.85, "as_of": "2026-10-10T19:00:00+00:00",
        "candles": [{"date": "d", "open": 1, "high": 2200.0, "low": 2000.0, "close": 1, "volume": 1}],
    }
    html = components.price_summary({"symbol": "TCS", "name": "Tata Consultancy Services"}, prices)
    assert "₹2,156.00" in html and "+80.00 (+3.85%)" in html and "pv-up" in html
    assert "₹2,200.00" in html and "₹2,000.00" in html


def test_notice_roles():
    assert 'role="alert"' in components.notice("t", "b", "error") and 'role="status"' in components.notice("t", "b")


def test_loading_placeholder_is_announced_as_busy():
    assert 'aria-busy="true"' in components.loading_placeholder("news") and "Loading" in components.loading_placeholder("quote")


def test_stock_pill_label_carries_direction_in_text():
    assert components.stock_pill_label({"symbol": "TCS", "change_pct": 3.85}) == "TCS +3.9%"
    assert components.stock_pill_label({"symbol": "INFY", "change_pct": -1.24}) == "INFY -1.2%"
    assert components.stock_pill_label({"symbol": "ITC", "change_pct": None}) == "ITC"


def test_caption_explains_the_list_and_the_session():
    top = {"mode": "active", "session_date": "2026-10-09", "universe": 213, "fallback": False}
    assert components.top_stocks_caption(top, "2026-10-09") == (
        "Stocks with the most money changing hands, out of 213 widely followed stocks. Based on today's trading (09 Oct)."
    )
    closed = components.top_stocks_caption(top, "2026-10-11")
    assert "last trading day (09 Oct)" in closed and "market is closed" in closed
    assert "F&O" not in closed
    assert components.top_stocks_caption({**top, "fallback": True}, "2026-10-11") == ""

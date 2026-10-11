"""HTML building blocks for the dashboard (no Streamlit and no business logic in here).

Everything that comes from outside (headlines, summaries, source names, URLs) is escaped here, because
article text arrives from third-party APIs and must be treated as untrusted.
"""

from __future__ import annotations

from html import escape
from urllib.parse import urlparse

from .formatting import format_day, format_rupees, format_signed, format_timestamp
from .theme import SENTIMENT_LABELS, SENTIMENT_ORDER

# The "What's moving today" lists, in the order they are offered.
MODE_LABELS = {"active": "Most traded", "gainers": "Top gainers", "losers": "Top losers"}
MODE_EXPLANATIONS = {
    "active": "Stocks with the most money changing hands",
    "gainers": "Stocks whose price rose the most",
    "losers": "Stocks whose price fell the most",
}


def safe_link_url(url: str | None) -> str:
    """Only plain http(s) links are ever rendered as hyperlinks."""
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return ""
    return url.strip() if parsed.scheme in ("http", "https") and parsed.netloc else ""


def _direction(change: float) -> str:
    return "up" if change > 0 else "down" if change < 0 else "flat"


def price_summary(stock: dict, prices: dict) -> str:
    candles = prices["candles"]
    period_high = max(c["high"] for c in candles)
    period_low = min(c["low"] for c in candles)
    direction = _direction(prices["change"])
    change_text = f'{format_signed(prices["change"])} ({format_signed(prices["change_pct"])}%)'
    facts = [
        ("Last close", format_rupees(prices["previous_close"])),
        ("Highest in this period", format_rupees(period_high)),
        ("Lowest in this period", format_rupees(period_low)),
        ("Last updated", format_timestamp(prices["as_of"])),
    ]
    facts_html = "".join(f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>" for label, value in facts)
    return (
        '<section class="pv-quote" aria-label="Price">'
        f'<p class="pv-id"><span class="pv-symbol">{escape(stock["symbol"])}</span>'
        f'<span class="pv-name">{escape(stock["name"])}</span></p>'
        '<p class="pv-now">'
        f'<span class="pv-price">{escape(format_rupees(prices["price"]))}</span>'
        f'<span class="pv-change pv-{direction}"><i class="pv-mark pv-m-{direction}" aria-hidden="true"></i>{escape(change_text)}</span>'
        "</p>"
        f'<dl class="pv-stats">{facts_html}</dl>'
        "</section>"
    )


def sentiment_summary(summary: dict) -> str:
    overall = summary["overall"]
    counts = summary["counts"]
    total = sum(counts.get(label, 0) for label in SENTIMENT_ORDER)
    if total == 0:
        return ""
    bar_segments = "".join(
        f'<span class="pv-seg pv-s-{label}" style="flex:{int(counts[label])}"></span>'
        for label in SENTIMENT_ORDER
        if counts.get(label, 0) > 0
    )
    legend = "".join(
        f'<li><i class="pv-mark pv-m-{label}" aria-hidden="true"></i>{int(counts.get(label, 0))} {label}</li>'
        for label in SENTIMENT_ORDER
    )
    description = ", ".join(f"{int(counts.get(label, 0))} {label}" for label in SENTIMENT_ORDER)
    noun = "headline" if total == 1 else "headlines"
    return (
        '<section class="pv-sentsum" aria-label="News mood summary">'
        '<div class="pv-overall">'
        f'<p class="pv-verdict pv-t-{escape(overall)}">{escape(SENTIMENT_LABELS[overall])}</p>'
        f'<p class="pv-score">Based on {total} {noun}</p>'
        "</div>"
        f'<div class="pv-stack" role="img" aria-label="{escape(description)}">{bar_segments}</div>'
        f'<ul class="pv-legend">{legend}</ul>'
        "</section>"
    )


def article_row(item: dict) -> str:
    sentiment = item["sentiment"]
    label = sentiment["label"]
    url = safe_link_url(item.get("url"))
    title = escape(item["title"])
    title_html = (
        f'<a class="pv-title" href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{title}</a>'
        if url
        else f'<span class="pv-title">{title}</span>'
    )
    summary = (item.get("summary") or "").strip()
    summary_html = f'<p class="pv-sum">{escape(summary)}</p>' if summary else ""
    byline = " | ".join(part for part in (item.get("source") or "", format_timestamp(item["published_at"])) if part)
    return (
        f'<article class="pv-row" data-sentiment="{escape(label)}">'
        '<div class="pv-sent">'
        f'<i class="pv-mark pv-m-{escape(label)}" aria-hidden="true"></i>'
        f'<span class="pv-sent-label">{escape(SENTIMENT_LABELS.get(label, label))}</span>'
        f'<span class="pv-conf">{sentiment["score"]:.0%} sure</span>'
        "</div>"
        f'<div class="pv-body">{title_html}{summary_html}<p class="pv-meta">{escape(byline)}</p></div>'
        "</article>"
    )


def article_list(items: list[dict]) -> str:
    return '<div class="pv-list">' + "".join(article_row(item) for item in items) + "</div>"


def stock_pill_label(stock: dict) -> str:
    """'RELIANCE +1.2%' (the sign carries the direction, so it never relies on colour)."""
    change_pct = stock.get("change_pct")
    return stock["symbol"] if change_pct is None else f'{stock["symbol"]} {change_pct:+.1f}%'


def top_stocks_caption(top: dict, today_iso: str) -> str:
    """One plain line saying what the list shows and which trading day it covers."""
    if top.get("fallback"):
        return ""
    day = format_day(top.get("session_date"))
    market_closed = bool(top.get("session_date")) and top["session_date"] != today_iso
    if market_closed:
        when = f"The market is closed now, so this is from the last trading day ({day})."
    else:
        when = f"Based on today's trading ({day})." if day else ""
    return f'{MODE_EXPLANATIONS[top["mode"]]}, out of {top["universe"]} widely followed stocks. {when}'.strip()


def notice(title: str, body: str, tone: str = "info") -> str:
    role = "alert" if tone == "error" else "status"
    return (
        f'<div class="pv-notice pv-n-{escape(tone)}" role="{role}">'
        f'<p class="pv-n-title">{escape(title)}</p><p class="pv-n-body">{escape(body)}</p></div>'
    )


def loading_placeholder(kind: str) -> str:
    """A grey placeholder shaped like the content that will replace it ("quote" or "news")."""
    if kind == "quote":
        blocks = (
            '<div class="pv-skel" style="width:14rem;height:1rem"></div>'
            '<div class="pv-skel" style="width:18rem;height:2.5rem"></div>'
            '<div class="pv-skel" style="width:100%;height:20rem"></div>'
        )
    else:
        rows = "".join(
            '<div class="pv-skel-row"><div class="pv-skel" style="height:1rem"></div>'
            '<div><div class="pv-skel" style="width:85%;height:1rem"></div>'
            '<div class="pv-skel" style="width:40%;height:0.75rem;margin-top:0.5rem"></div></div></div>'
            for _ in range(4)
        )
        blocks = '<div class="pv-skel" style="width:10rem;height:2rem"></div><div class="pv-skel" style="width:100%;height:0.75rem"></div>' + rows
    return f'<div class="pv-skeleton" aria-busy="true" aria-live="polite"><span class="pv-sr">Loading</span>{blocks}</div>'

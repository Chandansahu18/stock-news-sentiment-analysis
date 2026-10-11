"""Google News RSS: the free fallback news source (no API key, good coverage of Indian companies)."""

from __future__ import annotations

from datetime import timezone
from email.utils import parsedate_to_datetime

import requests
from defusedxml import ElementTree as ET  # safe against malicious XML

from . import http

RSS_URL = "https://news.google.com/rss/search"


class GoogleNewsError(Exception):
    """Failure fetching Google News (the message is safe to show to users)."""


def _to_utc_iso(rss_date: str | None) -> str | None:
    if not rss_date:
        return None
    try:
        return parsedate_to_datetime(rss_date).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def fetch_news(company_name: str, limit: int = 30) -> list[dict]:
    """Headlines from the last 7 days that mention the company, newest first as Google returns them."""
    params = {
        "q": f'"{company_name}" (stock OR shares OR results) when:7d',
        "hl": "en-IN",
        "gl": "IN",
        "ceid": "IN:en",
    }
    try:
        response = http.get(RSS_URL, params=params, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        feed = ET.fromstring(response.content)
    except (requests.RequestException, ET.ParseError) as exc:
        raise GoogleNewsError("We could not reach Google News. Please check your internet connection and try again.") from None

    articles = []
    for item in feed.iterfind("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        publisher = (item.findtext("source") or "Google News").strip()
        published_at = _to_utc_iso(item.findtext("pubDate"))
        if not title or not published_at:
            continue
        publisher_suffix = f" - {publisher}"
        if title.endswith(publisher_suffix):  # Google appends the publisher to every title
            title = title[: -len(publisher_suffix)].rstrip()
        articles.append({"title": title, "summary": "", "url": link, "source": publisher, "published_at": published_at})
        if len(articles) >= limit:
            break
    return articles

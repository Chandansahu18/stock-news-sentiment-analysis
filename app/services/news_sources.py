"""Choose where news comes from (Upstox first, Google News as the fallback), then clean the result."""

from __future__ import annotations

import logging
import re

from app.config import Settings
from app.integrations import google_news, upstox

log = logging.getLogger(__name__)


class NewsUnavailableError(Exception):
    """No news source could be reached (the message is safe to show to users)."""


def remove_duplicate_titles(articles: list[dict]) -> list[dict]:
    """Keep the first article for each headline, ignoring case and punctuation."""
    seen: set[str] = set()
    unique = []
    for article in articles:
        fingerprint = re.sub(r"[^a-z0-9]", "", article["title"].lower())
        if fingerprint and fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(article)
    return unique


def collect_articles(settings: Settings, company_name: str, instrument_key: str | None) -> tuple[list[dict], str]:
    """Return (articles newest first, name of the source that supplied them)."""
    articles: list[dict] = []
    source = ""
    last_error = ""
    wanted = settings.news_source

    if wanted in ("auto", "upstox"):
        if settings.upstox_token and instrument_key:
            try:
                articles = upstox.fetch_news(settings.upstox_token, instrument_key, settings.max_articles * 2)
                source = "upstox"
            except upstox.UpstoxError as exc:
                last_error = str(exc)
                log.warning("Upstox news failed: %s", exc)
        else:
            last_error = "Upstox news needs UPSTOX_ANALYTICS_TOKEN and a resolved instrument key"

    if not articles and wanted in ("auto", "google"):
        try:
            articles = google_news.fetch_news(company_name, settings.max_articles * 2)
            source = "google"
        except google_news.GoogleNewsError as exc:
            last_error = str(exc)
            log.warning("Google News failed: %s", exc)

    if not source:
        raise NewsUnavailableError(last_error or "No news source available")

    articles = remove_duplicate_titles(articles)
    articles.sort(key=lambda article: article["published_at"], reverse=True)
    return articles[: settings.max_articles], source

"""Get a stock's news from Google News RSS, keep only headlines about that stock, and clean the result."""

from __future__ import annotations

import logging
import re

from app.config import Settings
from app.integrations import google_news
from . import news_matching

log = logging.getLogger(__name__)

SOURCE_NAME = "google"
GOOGLE_RESULT_LIMIT = 100  # Google returns at most this many per search; most are dropped by the headline check


class NewsUnavailableError(Exception):
    """The news source could not be reached (the message is safe to show to users)."""


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


def collect_articles(settings: Settings, stock: dict) -> tuple[list[dict], str]:
    """Return (articles about this stock, newest first; name of the source). `stock` has "symbol" and "name"."""
    aliases = news_matching.aliases_for(stock)
    try:
        articles = google_news.fetch_news(aliases, GOOGLE_RESULT_LIMIT)
    except google_news.GoogleNewsError as exc:
        log.warning("Google News failed: %s", exc)
        raise NewsUnavailableError(str(exc)) from None

    is_about_stock = news_matching.headline_matcher(aliases)
    articles = [article for article in articles if is_about_stock(article["title"])]
    articles = remove_duplicate_titles(articles)
    articles.sort(key=lambda article: article["published_at"], reverse=True)
    return articles[: settings.max_articles], SOURCE_NAME

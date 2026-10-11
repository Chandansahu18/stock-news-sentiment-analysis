"""News with sentiment for one stock: fetch, score with FinBERT, cache, and summarize."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app import clock
from app.cache import get_cache
from app.concurrency import lock_for
from app.config import get_settings
from app.errors import DataUnavailableError
from app.integrations import finbert
from . import news_sources, stocks

# An average score above +0.15 (or below -0.15) on the -1..+1 scale counts as positive (or negative).
OVERALL_THRESHOLD = 0.15


def summarize_sentiment(scored_articles: list[dict]) -> dict:
    """Combine per-article sentiment into one summary for the stock."""
    counts = {label: 0 for label in finbert.SENTIMENT_LABELS}
    for item in scored_articles:
        counts[item["label"]] += 1
    article_count = len(scored_articles)
    average = round(sum(item["compound"] for item in scored_articles) / article_count, 4) if article_count else 0.0
    overall = "positive" if average > OVERALL_THRESHOLD else "negative" if average < -OVERALL_THRESHOLD else "neutral"
    return {"overall": overall, "average_score": average, "article_count": article_count, "counts": counts}


def filter_to_last_days(payload: dict, days: int | None, today: date | None = None) -> dict:
    """Keep only articles dated within the last `days` IST calendar days (1 = today) and re-summarize."""
    if not days:
        return payload
    today = today or clock.today_ist()
    first_day = today - timedelta(days=days - 1)
    kept = []
    for article in payload["articles"]:
        try:
            published_day = datetime.fromisoformat(article["published_at"]).astimezone(clock.IST).date()
        except (ValueError, KeyError):
            continue
        if published_day >= first_day:
            kept.append(article)
    summary = summarize_sentiment([article["sentiment"] for article in kept])
    return {**payload, "articles": kept, "summary": summary, "window_days": days}


def _text_for_model(article: dict) -> str:
    summary = article.get("summary") or ""
    return f"{article['title']}. {summary}".strip() if summary else article["title"]


def _article_id(article: dict) -> str:
    return article.get("url") or article["title"]


def _attach_sentiment(articles: list[dict], previous_payload: dict | None, model_name: str) -> None:
    """Add a "sentiment" to every article. Articles scored earlier are reused, so the model only runs on new ones."""
    known = {_article_id(a): a["sentiment"] for a in (previous_payload or {}).get("articles", [])}
    new_articles = [a for a in articles if _article_id(a) not in known]
    for article, result in zip(new_articles, finbert.score_texts([_text_for_model(a) for a in new_articles], model_name)):
        known[_article_id(article)] = result
    for article in articles:
        article["sentiment"] = known[_article_id(article)]


def get_news(symbol: str, refresh: bool = False, days: int | None = None) -> dict:
    """News for a stock, served from cache while fresh. `refresh=True` forces a re-fetch."""
    stock = stocks.find_stock(symbol)
    settings = get_settings()
    cache = get_cache()
    key = f"news_{stock['symbol']}"

    if not refresh:
        cached = cache.get_fresh(key, settings.news_ttl_seconds)
        if cached:
            return filter_to_last_days({**cached, "from_cache": True, "stale": False}, days)

    with lock_for(key):  # concurrent users of the same stock wait here instead of fetching twice
        if not refresh:  # someone else may have filled the cache while we waited
            cached = cache.get_fresh(key, settings.news_ttl_seconds)
            if cached:
                return filter_to_last_days({**cached, "from_cache": True, "stale": False}, days)

        previous = cache.get_even_if_expired(key)
        instrument_key = stock.get("key") if settings.upstox_token and settings.news_source != "google" else None
        try:
            articles, source = news_sources.collect_articles(settings, stock["name"], instrument_key)
        except news_sources.NewsUnavailableError as exc:
            if previous:  # serve the last good result instead of failing
                return filter_to_last_days({**previous, "from_cache": True, "stale": True, "warning": str(exc)}, days)
            raise DataUnavailableError(str(exc)) from None

        _attach_sentiment(articles, previous, settings.finbert_model)
        payload = {
            "symbol": stock["symbol"],
            "name": stock["name"],
            "source": source,
            "fetched_at": clock.now_utc_iso(),
            "summary": summarize_sentiment([article["sentiment"] for article in articles]),
            "articles": articles,
        }
        cache.save(key, payload)
        return filter_to_last_days({**payload, "from_cache": False, "stale": False}, days)

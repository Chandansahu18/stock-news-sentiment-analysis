"""Central configuration, read from environment variables (and a local .env file).

Every setting has a safe default, so the app starts with no configuration at all (news from Google,
no prices). See `.env.example` for the full list.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = PROJECT_ROOT / "watchlist.json"
load_dotenv(PROJECT_ROOT / ".env")

NEWS_SOURCES = {"auto", "upstox", "google"}
MIN_TOP_STOCKS, MAX_TOP_STOCKS = 10, 20


def _read_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    upstox_token: str
    news_source: str            # auto | upstox | google
    cache_dir: Path
    news_ttl_seconds: int       # how long scored news is served from cache
    price_ttl_seconds: int
    max_articles: int           # articles kept per stock
    top_stocks_count: int       # stocks per "today's stocks" list (10 to 20)
    top_stocks_ttl_seconds: int # how often the daily ranking is recomputed
    finbert_model: str          # a Hugging Face model id
    api_base_url: str           # where the dashboard finds the API
    preload_on_startup: bool    # load FinBERT and the stock list in the background at startup


def get_settings() -> Settings:
    cache_dir = Path(os.getenv("CACHE_DIR", "cache"))
    if not cache_dir.is_absolute():
        cache_dir = PROJECT_ROOT / cache_dir
    news_source = os.getenv("NEWS_SOURCE", "auto").strip().lower()
    if news_source not in NEWS_SOURCES:
        news_source = "auto"
    return Settings(
        upstox_token=os.getenv("UPSTOX_ANALYTICS_TOKEN", "").strip(),
        news_source=news_source,
        cache_dir=cache_dir,
        news_ttl_seconds=_read_int("NEWS_TTL_MINUTES", 30) * 60,
        price_ttl_seconds=_read_int("PRICE_TTL_MINUTES", 5) * 60,
        max_articles=max(1, min(_read_int("MAX_ARTICLES", 20), 100)),
        top_stocks_count=max(MIN_TOP_STOCKS, min(_read_int("TOP_STOCKS_COUNT", 20), MAX_TOP_STOCKS)),
        top_stocks_ttl_seconds=max(60, _read_int("TOP_STOCKS_TTL_MINUTES", 20) * 60),
        finbert_model=os.getenv("FINBERT_MODEL", "ProsusAI/finbert"),
        api_base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8010").rstrip("/"),
        preload_on_startup=_read_bool("PRELOAD_ON_STARTUP", True),
    )

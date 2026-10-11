"""The NSE stock list, from Upstox's public instruments file (no token needed).

One download gives us:
  * every NSE equity (symbol, name, instrument key) for search and lookups;
  * the F&O stock list (about 200 of the most liquid names), the universe for the daily ranking.
The parsed result is small, so it is cached on disk for a week.
"""

from __future__ import annotations

import gzip
import json
import re

import requests

from app.cache import JsonFileCache
from . import http

NSE_LISTING_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
CACHE_KEY = "nse_listing"
CACHE_MAX_AGE_SECONDS = 7 * 24 * 3600  # the list changes slowly
DOWNLOAD_TIMEOUT_SECONDS = 60
_COMPANY_SUFFIX = re.compile(r"\s+(LIMITED|LTD\.?)$", re.IGNORECASE)


def _clean_company_name(row: dict) -> str:
    name = (row.get("short_name") or row.get("name") or row.get("trading_symbol") or "").strip()
    if name.isupper() and len(name) > 5:  # "RELIANCE INDUSTRIES LTD" -> "Reliance Industries"
        name = name.title()
    return _COMPANY_SUFFIX.sub("", name).strip()


def parse_listing(rows: list[dict]) -> dict:
    """Reduce the raw ~77,000-row file to {"equities": [{symbol, name, key}], "fno_symbols": [symbol]}."""
    equities: dict[str, dict] = {}
    for row in rows:
        symbol = row.get("trading_symbol")
        is_main_board_equity = row.get("segment") == "NSE_EQ" and row.get("instrument_type") == "EQ"
        if is_main_board_equity and symbol and row.get("instrument_key"):
            equities[symbol] = {"symbol": symbol, "name": _clean_company_name(row), "key": row["instrument_key"]}
    fno_symbols = sorted(
        {
            row["underlying_symbol"]
            for row in rows
            if row.get("segment") == "NSE_FO"
            and row.get("instrument_type") == "FUT"
            and row.get("underlying_type") == "EQUITY"
            and row.get("underlying_symbol") in equities
        }
    )
    return {"equities": list(equities.values()), "fno_symbols": fno_symbols}


def download_rows() -> list[dict]:
    response = http.get(NSE_LISTING_URL, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()
    return json.loads(gzip.decompress(response.content))


def load_listing(cache: JsonFileCache) -> dict:
    """The parsed stock list, or {} if it is unavailable (offline with nothing cached)."""
    cached = cache.get_fresh(CACHE_KEY, CACHE_MAX_AGE_SECONDS)
    if cached:
        return cached
    try:
        listing = parse_listing(download_rows())
        if listing["equities"]:
            cache.save(CACHE_KEY, listing)
            return listing
    except (requests.RequestException, ValueError, OSError):
        pass
    return cache.get_even_if_expired(CACHE_KEY) or {}

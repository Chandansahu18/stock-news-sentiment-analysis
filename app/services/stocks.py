"""The stock directory: which stocks exist, how to look one up, and how search ranks matches."""

from __future__ import annotations

import json
import re
import time
from functools import lru_cache
from typing import NamedTuple

from app.cache import get_cache
from app.config import WATCHLIST_PATH
from app.errors import UnknownSymbolError
from app.integrations import nse_listing

LISTING_MEMORY_SECONDS = 3600  # keep the parsed list in memory this long before re-reading the disk cache
MAX_SEARCH_RESULTS = 20


class _Directory(NamedTuple):
    loaded_at: float
    listing: dict                    # {"equities": [...], "fno_symbols": [...]} as stored by nse_listing
    stocks_by_symbol: dict[str, dict]
    all_stocks: list[dict]


_directory: _Directory | None = None


@lru_cache(maxsize=1)
def _read_watchlist_file() -> tuple[dict, ...]:
    with open(WATCHLIST_PATH, encoding="utf-8") as handle:
        return tuple(json.load(handle))


def default_watchlist() -> list[dict]:
    """The curated stocks from watchlist.json: [{"symbol": "TCS", "name": "Tata Consultancy Services"}, ...].

    Shown when live rankings are unavailable. Their names also win over the exchange's names in search.
    """
    return [dict(stock) for stock in _read_watchlist_file()]


def _build_stocks_by_symbol(listing: dict) -> dict[str, dict]:
    curated_names = {stock["symbol"]: stock["name"] for stock in default_watchlist()}
    stocks = {
        equity["symbol"]: {**equity, "name": curated_names.get(equity["symbol"], equity["name"])}
        for equity in listing.get("equities", [])
    }
    if not stocks:  # offline with nothing cached: the curated list still works (news only, no prices)
        stocks = {symbol: {"symbol": symbol, "name": name, "key": None} for symbol, name in curated_names.items()}
    return stocks


def _get_directory() -> _Directory:
    global _directory
    if _directory and time.time() - _directory.loaded_at < LISTING_MEMORY_SECONDS:
        return _directory
    listing = nse_listing.load_listing(get_cache())
    stocks = _build_stocks_by_symbol(listing)
    directory = _Directory(time.time(), listing, stocks, list(stocks.values()))
    if listing:  # never remember a failed load
        _directory = directory
    return directory


def clear_listing_memo() -> None:
    """Forget the in-memory stock list (used by tests)."""
    global _directory
    _directory = None


def get_listing() -> dict:
    """The parsed NSE listing: {"equities": [...], "fno_symbols": [...]}."""
    return _get_directory().listing


def all_stocks() -> dict[str, dict]:
    """{symbol: {"symbol", "name", "key"}} for every NSE equity."""
    return _get_directory().stocks_by_symbol


def find_stock(symbol: str) -> dict:
    stock = all_stocks().get(symbol.strip().upper())
    if not stock:
        raise UnknownSymbolError(symbol)
    return stock


def rank_search_matches(stocks: list[dict], query: str, limit: int) -> list[dict]:
    """Best matches first: exact symbol, symbol prefix, name prefix, any word prefix, then substrings."""
    needle = query.strip().lower()
    if not needle:
        return []
    scored = []
    for stock in stocks:
        symbol, name = stock["symbol"].lower(), stock["name"].lower()
        if symbol == needle:
            rank = 0
        elif symbol.startswith(needle):
            rank = 1
        elif name.startswith(needle):
            rank = 2
        elif any(word.startswith(needle) for word in re.split(r"[^a-z0-9&]+", name)):
            rank = 3
        elif needle in symbol:
            rank = 4
        elif needle in name:
            rank = 5
        else:
            continue
        scored.append((rank, len(symbol), symbol, stock))
    scored.sort(key=lambda row: row[:3])
    return [{"symbol": stock["symbol"], "name": stock["name"]} for *_, stock in scored[:limit]]


def search_stocks(query: str, limit: int = 8) -> list[dict]:
    return rank_search_matches(_get_directory().all_stocks, query, max(1, min(limit, MAX_SEARCH_RESULTS)))

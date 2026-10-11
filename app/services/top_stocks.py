"""Today's top stocks: ranking from live quotes, cached once per IST day and refreshed every ~20 minutes."""

from __future__ import annotations

from collections import Counter

from app import clock
from app.cache import get_cache
from app.concurrency import lock_for
from app.config import get_settings
from app.integrations import upstox
from . import stocks

MODES = ("active", "gainers", "losers")
LATEST_KEY = "top_stocks_latest"
SESSION_SAMPLE_SIZE = 50  # the busiest N stocks decide which trading day the quotes belong to


class RankingError(Exception):
    """The ranking could not be built (the message is safe to show to users)."""


def rank_quotes(quotes: list[dict], count: int) -> dict[str, list[dict]]:
    """Three top-`count` lists from one set of quotes.

    active  : highest traded value (volume x average price), the stocks most likely to be in the news
    gainers : biggest % rise (only stocks that rose)
    losers  : biggest % fall (only stocks that fell)
    """
    traded = [quote for quote in quotes if quote["turnover"] > 0]
    return {
        "active": sorted(traded, key=lambda quote: quote["turnover"], reverse=True)[:count],
        "gainers": [q for q in sorted(traded, key=lambda q: q["change_pct"], reverse=True) if q["change_pct"] > 0][:count],
        "losers": [q for q in sorted(traded, key=lambda q: q["change_pct"]) if q["change_pct"] < 0][:count],
    }


def find_session_date(quotes: list[dict]) -> str | None:
    """The trading day the quotes belong to: the most common last-trade date among the busiest stocks."""
    busiest = sorted(quotes, key=lambda quote: quote["turnover"], reverse=True)[:SESSION_SAMPLE_SIZE]
    dates = Counter(quote["session_date"] for quote in busiest if quote.get("session_date"))
    return dates.most_common(1)[0][0] if dates else None


def build_ranking(token: str, listing: dict, count: int) -> dict:
    """Fetch quotes for the F&O stocks and return {"universe", "session_date", "lists"}."""
    equities_by_symbol = {equity["symbol"]: equity for equity in listing.get("equities", [])}
    universe = [equities_by_symbol[symbol] for symbol in listing.get("fno_symbols", []) if symbol in equities_by_symbol]
    if not universe:
        raise RankingError("The F&O stock list is not available yet")
    equity_by_key = {equity["key"]: equity for equity in universe}
    quotes = upstox.fetch_quotes(token, list(equity_by_key))
    if not quotes:
        raise RankingError("Upstox returned no quotes")
    lists = {}
    for mode, ranked_quotes in rank_quotes(quotes, count).items():
        lists[mode] = [
            {
                "symbol": equity_by_key[quote["key"]]["symbol"] if quote["key"] in equity_by_key else quote["symbol"],
                "name": equity_by_key[quote["key"]]["name"] if quote["key"] in equity_by_key else quote["symbol"],
                "price": quote["price"],
                "change_pct": quote["change_pct"],
                "turnover": round(quote["turnover"]),
            }
            for quote in ranked_quotes
        ]
    return {"universe": len(universe), "session_date": find_session_date(quotes), "lists": lists}


def _watchlist_fallback(reason: str) -> dict:
    """What we show when no live ranking exists: the curated watchlist, without prices."""
    watchlist = [
        {"symbol": s["symbol"], "name": s["name"], "price": None, "change_pct": None, "turnover": None}
        for s in stocks.default_watchlist()
    ]
    return {
        "date": clock.today_ist_iso(),
        "session_date": None,
        "as_of": clock.now_utc_iso(),
        "universe": len(watchlist),
        "lists": {mode: watchlist for mode in MODES},
        "fallback": True,
        "stale": False,
        "warning": reason,
    }


def _load_or_build_ranking(today: str) -> dict:
    settings = get_settings()
    cache = get_cache()
    key = f"top_stocks_{today}"

    cached = cache.get_fresh(key, settings.top_stocks_ttl_seconds)
    if cached is not None:
        return cached
    if not settings.upstox_token:
        return _watchlist_fallback("Live rankings need UPSTOX_ANALYTICS_TOKEN. Showing the default watchlist.")

    with lock_for(key):  # one user builds the ranking; the rest reuse it
        cached = cache.get_fresh(key, settings.top_stocks_ttl_seconds)
        if cached is not None:
            return cached
        try:
            built = build_ranking(settings.upstox_token, stocks.get_listing(), settings.top_stocks_count)
        except (upstox.UpstoxError, RankingError) as exc:
            previous = cache.get_even_if_expired(LATEST_KEY)
            if previous:
                return {**previous, "stale": True, "warning": str(exc)}
            return _watchlist_fallback(f"Live rankings are unavailable: {exc} Showing the default watchlist.")
        payload = {**built, "date": today, "as_of": clock.now_utc_iso(), "fallback": False, "stale": False, "warning": None}
        cache.save(key, payload)
        cache.save(LATEST_KEY, payload)
        return payload


def get_top_stocks(mode: str = "active") -> dict:
    payload = _load_or_build_ranking(clock.today_ist_iso())
    return {
        "mode": mode,
        "date": payload["date"],
        "session_date": payload.get("session_date"),
        "as_of": payload["as_of"],
        "universe": payload.get("universe", 0),
        "fallback": payload.get("fallback", False),
        "stale": payload.get("stale", False),
        "warning": payload.get("warning"),
        "stocks": payload["lists"].get(mode, []),
    }

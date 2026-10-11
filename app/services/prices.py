"""Daily price candles and the latest price for one stock (from Upstox)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app import clock
from app.cache import get_cache
from app.concurrency import lock_for
from app.config import get_settings
from app.errors import DataUnavailableError
from app.integrations import upstox
from . import stocks

MIN_DAYS, MAX_DAYS = 5, 365


def calculate_price_change(candles: list[dict], last_price: float | None, today_iso: str) -> dict:
    """Price, previous close and the change between them.

    When the last candle is already the latest session (today's candle, or the market is closed so the
    price equals the last close) the change compares that session with the one before it. Otherwise it
    would show a flat 0.00 all weekend.
    """
    last_close = candles[-1]["close"]
    price = last_price if last_price is not None else last_close
    last_candle_is_latest_session = candles[-1]["date"] == today_iso or abs(price - last_close) < 1e-9
    previous_close = candles[-2]["close"] if len(candles) > 1 and last_candle_is_latest_session else last_close
    change = round(price - previous_close, 2)
    return {
        "price": round(price, 2),
        "previous_close": round(previous_close, 2),
        "change": change,
        "change_pct": round(change / previous_close * 100, 2) if previous_close else 0.0,
    }


def _fetch_candles_and_last_price(token: str, instrument_key: str, days: int) -> tuple[list[dict], float | None]:
    """Both Upstox calls run at the same time, so the wait is the slower one instead of the sum."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        candles_call = pool.submit(upstox.fetch_candles, token, instrument_key, days)
        price_call = pool.submit(upstox.fetch_last_price, token, instrument_key)
        candles = candles_call.result()  # a failure here fails the whole request
        try:
            last_price = price_call.result()
        except upstox.UpstoxError:
            last_price = None  # candles alone are enough
    return candles, last_price


def get_prices(symbol: str, days: int = 30) -> dict:
    stock = stocks.find_stock(symbol)
    settings = get_settings()
    cache = get_cache()
    days = max(MIN_DAYS, min(days, MAX_DAYS))
    key = f"prices_{stock['symbol']}_{days}"

    cached = cache.get_fresh(key, settings.price_ttl_seconds)
    if cached:
        return {**cached, "stale": False}
    if not settings.upstox_token:
        raise DataUnavailableError(
            "Live prices are not set up yet. Add your Upstox key (UPSTOX_ANALYTICS_TOKEN) to the .env file "
            "(copy .env.example to .env if you do not have one), then restart the app."
        )
    if not stock.get("key"):
        raise DataUnavailableError("We could not find price data for this stock.")

    with lock_for(key):
        try:
            candles, last_price = _fetch_candles_and_last_price(settings.upstox_token, stock["key"], days)
        except upstox.UpstoxError as exc:
            older = cache.get_even_if_expired(key)
            if older:
                return {**older, "stale": True, "warning": str(exc)}
            raise DataUnavailableError(str(exc)) from None
        if not candles:
            raise DataUnavailableError("No prices were found for this period. Try a longer one.")

        payload = {
            "symbol": stock["symbol"],
            "name": stock["name"],
            "currency": "INR",
            **calculate_price_change(candles, last_price, clock.today_ist_iso()),
            "as_of": clock.now_utc_iso(),
            "candles": candles,
        }
        cache.save(key, payload)
        return {**payload, "stale": False}

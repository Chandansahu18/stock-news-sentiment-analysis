"""Upstox client: daily candles, last price and live quotes.

Uses a read-only Analytics Token as a Bearer token. The token is only ever placed in the
Authorization header; it is never logged or included in error messages.

Circuit breaker: if Upstox's firewall (Cloudflare) blocks us, every further request only extends the
block, so all Upstox calls are paused for a few minutes and fail instantly with a clear message.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from urllib.parse import quote as url_quote

import requests

from app.clock import IST, today_ist
from . import http

BASE_URL = "https://api.upstox.com"
BLOCK_COOLDOWN_SECONDS = 300

_blocked_until = 0.0  # epoch seconds; 0 means "not blocked"


class UpstoxError(Exception):
    """Any failure talking to Upstox (the message is safe to show to users)."""


def reset_block() -> None:
    global _blocked_until
    _blocked_until = 0.0


def _blocked_message() -> str:
    until = datetime.fromtimestamp(_blocked_until, IST).strftime("%H:%M")
    return (
        "Upstox is temporarily blocking requests from this network. We have paused price requests "
        f"until {until} IST to let the block clear. News still loads from Google."
    )


def _call_api(token: str, path: str, params: dict | None = None) -> dict:
    """GET one Upstox endpoint and return the parsed JSON body, or raise UpstoxError."""
    global _blocked_until
    if not token:
        raise UpstoxError(
            "Live prices are not set up yet. Add your Upstox key (UPSTOX_ANALYTICS_TOKEN) to the .env file, then restart the app."
        )
    if time.time() < _blocked_until:
        raise UpstoxError(_blocked_message())  # no request is sent while the breaker is open

    try:
        response = http.get(
            f"{BASE_URL}{path}",
            params=params,
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
        )
    except requests.RequestException:
        raise UpstoxError("We could not reach Upstox. Please check your internet connection and try again.") from None

    if response.status_code in (401, 403):
        if "html" in response.headers.get("content-type", "").lower():
            # A web page instead of JSON means the CDN/firewall blocked us, not that the token is wrong.
            _blocked_until = time.time() + BLOCK_COOLDOWN_SECONDS
            raise UpstoxError(_blocked_message())
        raise UpstoxError("Upstox rejected your access key. It may have expired, or it may not allow this kind of data.")
    if response.status_code == 429:
        raise UpstoxError("Upstox is getting too many requests right now. Please try again in a minute.")
    if response.status_code != 200:
        raise UpstoxError(f"Upstox had a problem (HTTP {response.status_code}). Please try again shortly.")
    try:
        body = response.json()
    except ValueError:
        raise UpstoxError("Upstox sent a reply we could not read. Please try again shortly.") from None
    if body.get("status") != "success":
        raise UpstoxError("Upstox reported an error. Please try again shortly.")
    return body


def fetch_candles(token: str, instrument_key: str, days: int = 30) -> list[dict]:
    """Daily OHLCV candles for the last `days` calendar days, oldest first."""
    today = today_ist()
    start = today - timedelta(days=days)
    path = f"/v3/historical-candle/{url_quote(instrument_key, safe='')}/days/1/{today:%Y-%m-%d}/{start:%Y-%m-%d}"
    body = _call_api(token, path)
    candles = []
    for row in (body.get("data") or {}).get("candles") or []:
        try:
            candles.append(
                {
                    "date": str(row[0])[:10],
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": int(row[5]),
                }
            )
        except (IndexError, TypeError, ValueError):
            continue  # skip a malformed row rather than failing the whole call
    candles.sort(key=lambda candle: candle["date"])
    return candles


def fetch_last_price(token: str, instrument_key: str) -> float | None:
    """Last traded price, or None if unavailable (callers fall back to the last close)."""
    body = _call_api(token, "/v2/market-quote/ltp", {"instrument_key": instrument_key})
    for entry in (body.get("data") or {}).values():
        price = entry.get("last_price") if isinstance(entry, dict) else None
        if isinstance(price, (int, float)):
            return float(price)
    return None


def _trading_day_of(entry: dict) -> str | None:
    """The trading day of a quote ('YYYY-MM-DD', IST), from its last trade time or its timestamp."""
    try:
        return datetime.fromtimestamp(int(entry["last_trade_time"]) / 1000, tz=IST).date().isoformat()
    except (KeyError, TypeError, ValueError, OSError):
        stamp = entry.get("timestamp")
        return str(stamp)[:10] if stamp else None


def fetch_quotes(token: str, instrument_keys: list[str], batch_size: int = 100) -> list[dict]:
    """Live quotes for many instruments, in small batches (very long URLs get blocked by the firewall).

    Returns [{key, symbol, price, change_pct, volume, turnover, session_date}]. Raises UpstoxError if any
    batch fails, because a partial set would give a misleading ranking.
    """
    quotes = []
    for start in range(0, len(instrument_keys), batch_size):
        if start:
            time.sleep(0.25)  # stay well under the rate limits
        batch = instrument_keys[start : start + batch_size]
        body = _call_api(token, "/v2/market-quote/quotes", {"instrument_key": ",".join(batch)})
        for entry in (body.get("data") or {}).values():
            if not isinstance(entry, dict):
                continue
            price, net_change, volume = entry.get("last_price"), entry.get("net_change"), entry.get("volume")
            if not all(isinstance(value, (int, float)) for value in (price, net_change, volume)):
                continue
            previous_close = price - net_change
            average_price = entry.get("average_price")
            unit_price = average_price if isinstance(average_price, (int, float)) and average_price > 0 else price
            quotes.append(
                {
                    "key": entry.get("instrument_token"),
                    "symbol": entry.get("symbol"),
                    "price": float(price),
                    "change_pct": round(net_change / previous_close * 100, 2) if previous_close > 0 else 0.0,
                    "volume": int(volume),
                    "turnover": float(volume) * float(unit_price),  # traded value = volume x average price
                    "session_date": _trading_day_of(entry),
                }
            )
    return quotes


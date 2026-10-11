"""The dashboard's only way to reach the backend: HTTP calls to the FastAPI service.

Responses are kept in a small in-memory cache for a minute. It is shared by every browser session and is
safe to use from several threads, which is what lets the price and the news load at the same time.
Failed calls are never cached, so a temporary error disappears as soon as the backend recovers.
"""

from __future__ import annotations

import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import requests

from app.config import get_settings

CACHE_SECONDS = 60
MAX_CACHE_ENTRIES = 256
REQUEST_TIMEOUT_SECONDS = 180  # the first call for a stock fetches and scores news, which can take a while

_cache: dict[tuple, tuple[float, object]] = {}
_cache_lock = threading.Lock()


class ApiError(Exception):
    """The backend could not be reached or answered with an error (the message is safe to show)."""


def call_api(method: str, path: str, params: dict | None = None, timeout: int = REQUEST_TIMEOUT_SECONDS):
    """One HTTP call to the backend, returning the parsed JSON or raising ApiError."""
    base_url = get_settings().api_base_url
    try:
        response = requests.request(method, f"{base_url}{path}", params=params, timeout=timeout)
    except requests.RequestException:
        raise ApiError(
            f"The dashboard cannot reach the API at {base_url}. Start it with: "
            "uvicorn app.main:app --host 127.0.0.1 --port 8010"
        ) from None
    if response.status_code != 200:
        try:
            detail = response.json().get("detail", "")
        except ValueError:
            detail = ""
        raise ApiError(detail if isinstance(detail, str) and detail else f"The API returned an error (HTTP {response.status_code}).")
    return response.json()


def get_cached(path: str, **params):
    """GET with a one-minute cache. The returned data is a private copy, so callers may change it freely."""
    key = (path, tuple(sorted(params.items())))
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return copy.deepcopy(hit[1])
    data = call_api("GET", path, params or None)  # outside the lock: slow calls must not block other users
    with _cache_lock:
        if len(_cache) >= MAX_CACHE_ENTRIES:
            _cache.pop(min(_cache, key=lambda k: _cache[k][0]))  # drop the oldest entry
        _cache[key] = (time.time(), copy.deepcopy(data))
    return data


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def fetch_concurrently(calls: dict[str, tuple[str, dict]]) -> dict[str, object]:
    """Run several cached GETs at the same time: {name: (path, params)} -> {name: data or ApiError}.

    A failed call returns its ApiError instead of raising, so one failure never hides the other results.
    """
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = {name: pool.submit(get_cached, path, **params) for name, (path, params) in calls.items()}
    results = {}
    for name, future in futures.items():
        try:
            results[name] = future.result()
        except ApiError as error:
            results[name] = error
    return results


def stock_path(symbol: str, endpoint: str) -> str:
    """'/stocks/TCS/news' (the symbol is URL-encoded, so it can never alter the path)."""
    return f"/stocks/{quote(symbol, safe='')}/{endpoint}"

from pathlib import Path
import threading

import requests
from streamlit.testing.v1 import AppTest

from tests.helpers import FakeResponse
from ui import api_client

ROOT = Path(__file__).resolve().parent.parent

ARTICLES = [
    {
        "title": "TCS wins deal", "summary": "", "url": "https://example.com/1", "source": "Mint",
        "published_at": "2026-10-09T10:00:00+00:00",
        "sentiment": {"label": "positive", "score": 0.9, "compound": 0.8, "probs": {"positive": 0.9, "neutral": 0.05, "negative": 0.05}},
    },
    {
        "title": "TCS faces probe", "summary": "", "url": "https://example.com/2", "source": "ET",
        "published_at": "2026-10-09T09:00:00+00:00",
        "sentiment": {"label": "negative", "score": 0.8, "compound": -0.7, "probs": {"positive": 0.1, "neutral": 0.1, "negative": 0.8}},
    },
]
TOP = [
    {"symbol": "TCS", "name": "Tata Consultancy Services", "price": 2156.0, "change_pct": 3.85, "turnover": 900},
    {"symbol": "INFY", "name": "Infosys", "price": 1500.0, "change_pct": -1.2, "turnover": 800},
]


def _news(articles, days):
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for a in articles:
        counts[a["sentiment"]["label"]] += 1
    return {
        "symbol": "TCS", "name": "x", "source": "upstox", "fetched_at": "2026-10-10T19:00:00+00:00", "stale": False, "from_cache": True,
        "window_days": days,
        "summary": {"overall": "neutral", "average_score": 0.05, "article_count": len(articles), "counts": counts},
        "articles": articles,
    }


def _fake_request(articles_by_days=None, fail_prices=False, fallback=False, calls=None):
    if articles_by_days is None:
        articles_by_days = {1: ARTICLES, 7: ARTICLES}

    def fake(method, url, params=None, timeout=None):
        path = url.split("8010", 1)[-1]
        if calls is not None:
            calls.append((method, path, dict(params or {})))
        if path == "/stocks/top":
            return FakeResponse(json_data={
                "mode": (params or {}).get("mode", "active"), "date": "2026-10-11", "session_date": None if fallback else "2026-10-09",
                "as_of": "2026-10-11T07:00:00+00:00", "universe": 5, "fallback": fallback, "stale": False,
                "warning": "Live rankings need UPSTOX_ANALYTICS_TOKEN." if fallback else None, "stocks": TOP,
            })
        if path == "/stocks/search":
            q = (params or {}).get("q", "").lower()
            return FakeResponse(json_data=[s for s in TOP if q in s["name"].lower() or q in s["symbol"].lower()])
        if path.endswith("/prices"):
            if fail_prices:
                return FakeResponse(status_code=503, json_data={"detail": "UPSTOX_ANALYTICS_TOKEN is not set."})
            return FakeResponse(json_data={
                "symbol": "TCS", "name": "x", "currency": "INR", "price": 2156.0, "previous_close": 2076.0, "change": 80.0,
                "change_pct": 3.85, "as_of": "2026-10-10T19:00:00+00:00", "stale": False,
                "candles": [{"date": "2026-10-08", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1}],
            })
        days = (params or {}).get("days")
        return FakeResponse(json_data=_news(articles_by_days.get(days, []), days))
    return fake


def _run(monkeypatch, **kw):
    api_client.clear_cache()  # the dashboard remembers API answers across runs inside one process
    monkeypatch.setattr(requests, "request", _fake_request(**kw))
    return AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=30).run()


def _labels(at):
    return {c.label for c in at.get("segmented_control")} | {c.label for c in at.get("pills")}


def _html(at):
    return " ".join(str(e.value) for e in at.get("html"))


def test_dashboard_shows_search_and_todays_stocks(monkeypatch):
    at = _run(monkeypatch)
    assert not at.exception
    assert at.text_input[0].label == "Search stocks"
    assert {"Today's stocks", "Pick a stock", "Price range", "News from", "Show"} <= _labels(at)
    assert at.button[0].label == "Refresh news"
    pick = [p for p in at.get("pills") if p.label == "Pick a stock"][0]
    assert pick.value == "TCS"  # the first stock of the ranking is selected by default


def test_search_box_calls_the_api_and_shows_matches(monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "request", _fake_request(calls=calls))
    api_client.clear_cache()
    at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=30).run()
    at.text_input[0].set_value("infos").run()
    assert not at.exception
    assert ("GET", "/stocks/search", {"q": "infos", "limit": 8}) in calls
    assert "Search results" in _labels(at)


def test_search_with_no_match_says_so(monkeypatch):
    at = _run(monkeypatch)
    at.text_input[0].set_value("zzzz").run()
    assert not at.exception and "No NSE stock matches" in _html(at)


def test_news_window_widens_when_nothing_is_dated_today(monkeypatch):
    at = _run(monkeypatch, articles_by_days={1: [], 7: ARTICLES})
    assert not at.exception
    html = _html(at)
    assert "No articles for the selected period" in html and "TCS wins deal" in html


def test_dashboard_falls_back_when_rankings_are_unavailable(monkeypatch):
    at = _run(monkeypatch, fallback=True)
    assert not at.exception and "Showing the default watchlist" in _html(at)


def test_dashboard_handles_missing_token_and_empty_news(monkeypatch):
    at = _run(monkeypatch, articles_by_days={}, fail_prices=True)
    assert not at.exception  # both states are shown inline, not as a crash
    assert "Price data is unavailable" in _html(at) and "No recent news" in _html(at)



def test_price_and_news_are_requested_at_the_same_time(monkeypatch):
    """Each of the two calls waits for the other at a barrier; if the page asked one after the other, this would fail."""
    barrier = threading.Barrier(2, timeout=5)
    inner = _fake_request()

    def fake(method, url, params=None, timeout=None):
        if url.endswith("/prices") or url.endswith("/news"):
            barrier.wait()
        return inner(method, url, params=params, timeout=timeout)

    api_client.clear_cache()
    monkeypatch.setattr(requests, "request", fake)
    at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=30).run()
    assert not at.exception
    html = _html(at)
    assert "TCS wins deal" in html and "pv-quote" in html


def test_refresh_button_asks_the_backend_to_refetch_then_reloads(monkeypatch):
    calls = []
    api_client.clear_cache()
    monkeypatch.setattr(requests, "request", _fake_request(calls=calls))
    at = AppTest.from_file(str(ROOT / "dashboard.py"), default_timeout=30).run()
    at.button[0].click().run()
    assert not at.exception
    assert any(method == "POST" and path == "/stocks/TCS/refresh" for method, path, _ in calls)

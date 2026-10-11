import threading

from app import clock
from app.integrations import upstox
from app.services import prices


def make_candles(*closes_by_date):
    return [{"date": d, "open": 1, "high": 1, "low": 1, "close": c, "volume": 1} for d, c in closes_by_date]


# ---------- the change calculation ----------

def test_change_compares_with_the_session_before_when_the_last_candle_is_today():
    candles = make_candles(("2026-01-01", 100.0), ("2026-10-12", 105.0))
    result = prices.calculate_price_change(candles, 110.0, today_iso="2026-10-12")
    assert result == {"price": 110.0, "previous_close": 100.0, "change": 10.0, "change_pct": 10.0}


def test_change_before_the_market_has_traded_today_compares_with_the_last_close():
    candles = make_candles(("2026-10-08", 200.0), ("2026-10-09", 210.0))
    result = prices.calculate_price_change(candles, 215.0, today_iso="2026-10-12")  # candle is not today's, price differs
    assert result["previous_close"] == 210.0 and result["change"] == 5.0


def test_market_closed_shows_the_last_sessions_change_not_a_flat_zero():
    candles = make_candles(("2026-10-08", 200.0), ("2026-10-09", 210.0))
    result = prices.calculate_price_change(candles, 210.0, today_iso="2026-10-11")  # weekend: price equals the last close
    assert result["price"] == 210.0 and result["previous_close"] == 200.0 and result["change"] == 10.0


def test_missing_last_price_falls_back_to_the_last_close():
    candles = make_candles(("2026-10-08", 200.0), ("2026-10-09", 210.0))
    assert prices.calculate_price_change(candles, None, "2026-10-11")["price"] == 210.0


# ---------- the endpoint ----------

def test_prices_need_a_token(client):
    response = client.get("/stocks/TCS/prices")
    assert response.status_code == 503 and "UPSTOX_ANALYTICS_TOKEN" in response.json()["detail"]


def test_days_is_validated(client):
    assert client.get("/stocks/TCS/prices?days=1").status_code == 422
    assert client.get("/stocks/TCS/prices?days=9999").status_code == 422


def test_prices_with_a_token(client, monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "tok")
    candles = make_candles(("2026-01-01", 100.0), (clock.today_ist_iso(), 105.0))
    monkeypatch.setattr(upstox, "fetch_candles", lambda token, key, days: candles)
    monkeypatch.setattr(upstox, "fetch_last_price", lambda token, key: 110.0)
    body = client.get("/stocks/TCS/prices?days=30").json()
    assert body["price"] == 110.0 and body["previous_close"] == 100.0
    assert body["change"] == 10.0 and len(body["candles"]) == 2


def test_candles_and_last_price_are_fetched_at_the_same_time(client, monkeypatch):
    """Both calls wait for each other at a barrier; if they ran one after the other, this would time out."""
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "tok")
    barrier = threading.Barrier(2, timeout=3)

    def fetch_candles(token, key, days):
        barrier.wait()
        return make_candles(("2026-10-09", 210.0))

    def fetch_last_price(token, key):
        barrier.wait()
        return 211.0

    monkeypatch.setattr(upstox, "fetch_candles", fetch_candles)
    monkeypatch.setattr(upstox, "fetch_last_price", fetch_last_price)
    assert client.get("/stocks/TCS/prices?days=30").json()["price"] == 211.0


def test_a_failed_last_price_does_not_fail_the_request(client, monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "tok")
    monkeypatch.setattr(upstox, "fetch_candles", lambda token, key, days: make_candles(("2026-10-09", 210.0)))

    def price_down(token, key):
        raise upstox.UpstoxError("down")

    monkeypatch.setattr(upstox, "fetch_last_price", price_down)
    assert client.get("/stocks/TCS/prices?days=30").json()["price"] == 210.0


def test_older_prices_are_served_when_upstox_fails(client, monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "tok")
    monkeypatch.setattr(upstox, "fetch_candles", lambda token, key, days: make_candles(("2026-01-01", 1.0)))
    monkeypatch.setattr(upstox, "fetch_last_price", lambda token, key: None)
    assert client.get("/stocks/TCS/prices?days=30").status_code == 200
    monkeypatch.setenv("PRICE_TTL_MINUTES", "0")  # expire the cache, then make Upstox fail

    def upstox_down(token, key, days):
        raise upstox.UpstoxError("down")

    monkeypatch.setattr(upstox, "fetch_candles", upstox_down)
    body = client.get("/stocks/TCS/prices?days=30").json()
    assert body["stale"] is True and body["warning"] == "down"

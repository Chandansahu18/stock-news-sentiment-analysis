import pytest

from app import clock
from app.cache import get_cache
from app.integrations import upstox
from app.services import top_stocks


def make_quote(key, symbol, turnover, change_pct):
    return {"key": key, "symbol": symbol, "price": 100.0, "change_pct": change_pct, "turnover": turnover, "volume": 1, "session_date": "2026-10-09"}


QUOTES = [
    make_quote("k1", "A", 900.0, 1.0),
    make_quote("k2", "B", 500.0, 5.0),
    make_quote("k3", "C", 100.0, -4.0),
    make_quote("k4", "D", 0.0, 9.0),
    make_quote("k5", "E", 300.0, 0.0),
]

GOOD_RANKING = {
    "universe": 5,
    "session_date": "2026-10-09",
    "lists": {
        "active": [{"symbol": "TCS", "name": "TCS", "price": 1.0, "change_pct": 1.0, "turnover": 5}],
        "gainers": [{"symbol": "INFY", "name": "Infosys", "price": 2.0, "change_pct": 3.0, "turnover": 4}],
        "losers": [],
    },
}


# ---------- ranking ----------

def test_rank_quotes_builds_three_lists():
    lists = top_stocks.rank_quotes(QUOTES, count=2)
    assert [q["symbol"] for q in lists["active"]] == ["A", "B"]
    assert [q["symbol"] for q in lists["gainers"]] == ["B", "A"]  # D has no volume, E did not rise
    assert [q["symbol"] for q in lists["losers"]] == ["C"]        # only stocks that fell


def test_session_date_is_the_busiest_stocks_majority():
    quotes = [make_quote("a", "A", 9.0, 0), make_quote("b", "B", 8.0, 0), {**make_quote("c", "C", 7.0, 0), "session_date": "2026-10-08"}]
    assert top_stocks.find_session_date(quotes) == "2026-10-09"
    assert top_stocks.find_session_date([]) is None


def test_build_ranking_maps_names_and_needs_a_universe(monkeypatch):
    listing = {"equities": [{"symbol": "A", "name": "Alpha", "key": "k1"}, {"symbol": "B", "name": "Beta", "key": "k2"}], "fno_symbols": ["A", "B"]}
    monkeypatch.setattr(upstox, "fetch_quotes", lambda token, keys: [q for q in QUOTES if q["key"] in keys])
    built = top_stocks.build_ranking("tok", listing, 10)
    assert built["universe"] == 2
    assert built["lists"]["active"][0] == {"symbol": "A", "name": "Alpha", "price": 100.0, "change_pct": 1.0, "turnover": 900}
    with pytest.raises(top_stocks.RankingError):
        top_stocks.build_ranking("tok", {"equities": [], "fno_symbols": []}, 10)


# ---------- the cached daily list ----------

def test_without_a_token_the_default_watchlist_is_shown(client):
    body = client.get("/stocks/top").json()
    assert body["fallback"] is True and "UPSTOX_ANALYTICS_TOKEN" in body["warning"]
    assert len(body["stocks"]) >= 10 and body["stocks"][0]["price"] is None


def test_one_scan_per_day_serves_all_three_modes(client, monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "tok")
    counts_requested = []

    def fake_build(token, listing, count):
        counts_requested.append(count)
        return GOOD_RANKING

    monkeypatch.setattr(top_stocks, "build_ranking", fake_build)
    active = client.get("/stocks/top?mode=active").json()
    gainers = client.get("/stocks/top?mode=gainers").json()
    losers = client.get("/stocks/top?mode=losers").json()
    assert active["fallback"] is False and active["stocks"][0]["symbol"] == "TCS" and active["session_date"] == "2026-10-09"
    assert gainers["stocks"][0]["symbol"] == "INFY" and losers["stocks"] == []
    assert counts_requested == [20]  # one Upstox scan served all three modes
    assert get_cache().get_even_if_expired(f"top_stocks_{clock.today_ist_iso()}") is not None  # keyed by the IST date
    assert client.get("/stocks/top?mode=bogus").status_code == 422


def test_last_good_list_is_served_when_upstox_fails(client, monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "tok")
    monkeypatch.setattr(top_stocks, "build_ranking", lambda token, listing, count: GOOD_RANKING)
    client.get("/stocks/top")
    monkeypatch.setattr(clock, "today_ist_iso", lambda: "2099-01-01")  # a new day, so today's list does not exist yet

    def blocked(token, listing, count):
        raise upstox.UpstoxError("firewall")

    monkeypatch.setattr(top_stocks, "build_ranking", blocked)
    body = client.get("/stocks/top").json()
    assert body["stale"] is True and body["warning"] == "firewall" and body["stocks"][0]["symbol"] == "TCS"


def test_with_no_previous_list_it_falls_back_and_says_why(client, monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "tok")

    def blocked(token, listing, count):
        raise upstox.UpstoxError("firewall")

    monkeypatch.setattr(top_stocks, "build_ranking", blocked)
    body = client.get("/stocks/top").json()
    assert body["fallback"] is True and "firewall" in body["warning"]

from app.errors import UnknownSymbolError
from app.integrations import finbert, nse_listing
from app.services import news_sources, stocks
from tests.helpers import fake_score_texts

import pytest

SAMPLE = [
    {"symbol": "INFY", "name": "Infosys"},
    {"symbol": "INFOBEAN", "name": "Infobeans Technologies"},
    {"symbol": "TCS", "name": "Tata Consultancy Services"},
    {"symbol": "M&M", "name": "Mahindra & Mahindra"},
]


def symbols(matches):
    return [m["symbol"] for m in matches]


# ---------- ranking of matches ----------

def test_exact_symbol_beats_prefixes_and_shorter_symbols_come_first():
    assert symbols(stocks.rank_search_matches(SAMPLE, "infy", 5)) == ["INFY"]
    assert symbols(stocks.rank_search_matches(SAMPLE, "inf", 5)) == ["INFY", "INFOBEAN"]


def test_matches_a_word_inside_the_company_name_and_special_characters():
    assert symbols(stocks.rank_search_matches(SAMPLE, "consultancy", 5)) == ["TCS"]
    assert symbols(stocks.rank_search_matches(SAMPLE, "m&m", 5)) == ["M&M"]


def test_blank_or_unmatched_queries_return_nothing_and_limit_is_applied():
    assert stocks.rank_search_matches(SAMPLE, "   ", 5) == []
    assert stocks.rank_search_matches(SAMPLE, "zzz", 5) == []
    assert len(stocks.rank_search_matches(SAMPLE, "i", 2)) == 2


# ---------- the stock directory ----------

def test_curated_names_win_over_the_exchange_names():
    assert stocks.find_stock("tcs")["name"] == "Tata Consultancy Services"  # watchlist.json says so; the listing says "TCS"
    assert stocks.find_stock(" infy ")["key"] == "NSE_EQ|INE009A01021"      # case and spaces are forgiven


def test_unknown_symbol_raises():
    with pytest.raises(UnknownSymbolError):
        stocks.find_stock("NOTLISTED")


def test_without_a_listing_the_curated_watchlist_still_works_and_nothing_is_remembered(monkeypatch):
    monkeypatch.setattr(nse_listing, "load_listing", lambda cache: {})
    assert stocks.find_stock("TCS")["key"] is None  # news works, prices need the key
    with pytest.raises(UnknownSymbolError):
        stocks.find_stock("INFOBEAN")
    monkeypatch.undo()  # the real listing becomes available again
    stocks.clear_listing_memo()


def test_the_listing_is_loaded_once_not_on_every_lookup(monkeypatch):
    loads = []
    monkeypatch.setattr(nse_listing, "load_listing", lambda cache: loads.append(1) or {"equities": [{"symbol": "TCS", "name": "TCS", "key": "k"}], "fno_symbols": []})
    for _ in range(5):
        stocks.find_stock("TCS")
        stocks.search_stocks("tc")
    assert len(loads) == 1


# ---------- the HTTP endpoints ----------

def test_search_endpoint(client):
    assert client.get("/stocks/search", params={"q": "reli"}).json() == [{"symbol": "RELIANCE", "name": "Reliance Industries"}]
    assert client.get("/stocks/search", params={"q": "tata"}).json()[0]["symbol"] == "TCS"  # curated name wins


def test_search_input_is_validated(client):
    assert client.get("/stocks/search", params={"q": ""}).status_code == 422
    assert client.get("/stocks/search", params={"q": "x" * 41}).status_code == 422
    assert client.get("/stocks/search", params={"q": "i", "limit": 99}).status_code == 422


def test_any_listed_stock_is_accepted_not_just_the_watchlist(client, monkeypatch):
    monkeypatch.setattr(news_sources, "collect_articles", lambda settings, name, key: ([], "google"))
    monkeypatch.setattr(finbert, "score_texts", fake_score_texts)
    assert client.get("/stocks/INFOBEAN/news").status_code == 200  # not in watchlist.json
    assert client.get("/stocks/NOTLISTED/news").status_code == 404

import pytest

from app.config import get_settings
from app.integrations import google_news, upstox
from app.services import news_sources
from tests.helpers import make_article

TCS = {"symbol": "TCS", "name": "Tata Consultancy Services", "key": "NSE_EQ|X"}
HPCL = {"symbol": "HINDPETRO", "name": "Hindustan Petroleum Corp", "key": "NSE_EQ|INE094A01015"}


def test_news_comes_from_google_and_is_cleaned(monkeypatch):
    monkeypatch.setattr(
        google_news, "fetch_news",
        lambda terms, limit: [make_article("TCS A", "u1"), make_article("tcs a!", "u2"), make_article("TCS B", "u3", "2026-10-10T00:00:00+00:00")],
    )
    articles, source = news_sources.collect_articles(get_settings(), TCS)
    assert source == "google"
    assert [a["title"] for a in articles] == ["TCS B", "TCS A"]  # "tcs a!" is a duplicate of "TCS A"; newest first


def test_only_headlines_about_the_stock_are_kept(monkeypatch):
    monkeypatch.setattr(
        google_news, "fetch_news",
        lambda terms, limit: [
            make_article("HPCL taps Technip Energies for EPC on new Mumbai refinery unit", "u1"),
            make_article("Can RBI's six forex measures help stabilise the rupee?", "u2"),
            make_article("360 One Quant Fund - Regular Plan - Growth", "u3"),
            make_article("Buy, Sell Or Hold: ITC, HPCL, Reliance Industries and Wipro", "u4"),
            make_article("Hindustan Petroleum’s Vizag refinery restarts unit", "u5"),
        ],
    )
    articles, _ = news_sources.collect_articles(get_settings(), HPCL)
    assert [a["url"] for a in articles] == ["u1", "u4", "u5"]


def test_google_is_asked_about_every_name_of_the_stock(monkeypatch):
    asked = []
    monkeypatch.setattr(google_news, "fetch_news", lambda terms, limit: asked.append((list(terms), limit)) or [])
    news_sources.collect_articles(get_settings(), HPCL)
    terms, limit = asked[0]
    assert {"Hindustan Petroleum", "HPCL"} <= set(terms)
    assert limit == news_sources.GOOGLE_RESULT_LIMIT  # ask for everything: the check below drops most of it


def test_a_stock_with_no_matching_headlines_gets_an_empty_list_not_other_news(monkeypatch):
    monkeypatch.setattr(google_news, "fetch_news", lambda terms, limit: [make_article("Rupee falls on oil prices", "u1")])
    assert news_sources.collect_articles(get_settings(), HPCL)[0] == []


def test_the_number_of_articles_is_capped_after_the_check(monkeypatch):
    monkeypatch.setenv("MAX_ARTICLES", "3")
    monkeypatch.setattr(
        google_news, "fetch_news",
        lambda terms, limit: [make_article(f"Unrelated {i}", f"x{i}") for i in range(50)] + [make_article(f"TCS news {i}", f"u{i}") for i in range(10)],
    )
    articles = news_sources.collect_articles(get_settings(), TCS)[0]
    assert len(articles) == 3 and all("TCS" in a["title"] for a in articles)


def test_a_google_failure_becomes_news_unavailable(monkeypatch):
    def google_down(terms, limit):
        raise google_news.GoogleNewsError("offline")

    monkeypatch.setattr(google_news, "fetch_news", google_down)
    with pytest.raises(news_sources.NewsUnavailableError, match="offline"):
        news_sources.collect_articles(get_settings(), TCS)


def test_news_never_calls_upstox_even_with_a_token(monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "tok")
    monkeypatch.setattr(upstox, "_call_api", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Upstox was called")))
    monkeypatch.setattr(google_news, "fetch_news", lambda terms, limit: [make_article("TCS G", "u")])
    assert news_sources.collect_articles(get_settings(), TCS)[1] == "google"

import pytest

from app.config import get_settings
from app.integrations import google_news, upstox
from app.services import news_sources
from tests.helpers import make_article


def test_falls_back_to_google_when_upstox_fails_and_cleans_the_result(monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "tok")

    def upstox_down(token, key, limit):
        raise upstox.UpstoxError("denied")

    monkeypatch.setattr(upstox, "fetch_news", upstox_down)
    monkeypatch.setattr(
        google_news, "fetch_news",
        lambda name, limit: [make_article("A", "u1"), make_article("a!", "u2"), make_article("B", "u3", "2026-10-10T00:00:00+00:00")],
    )
    articles, source = news_sources.collect_articles(get_settings(), "TCS", "NSE_EQ|X")
    assert source == "google"
    assert [a["title"] for a in articles] == ["B", "A"]  # "a!" is a duplicate of "A"; newest first


def test_prefers_upstox(monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "tok")
    monkeypatch.setattr(upstox, "fetch_news", lambda token, key, limit: [make_article("From Upstox", "u")])
    articles, source = news_sources.collect_articles(get_settings(), "TCS", "NSE_EQ|X")
    assert source == "upstox" and articles[0]["title"] == "From Upstox"


def test_raises_when_every_source_fails(monkeypatch):
    def google_down(name, limit):
        raise google_news.GoogleNewsError("offline")

    monkeypatch.setattr(google_news, "fetch_news", google_down)
    with pytest.raises(news_sources.NewsUnavailableError):
        news_sources.collect_articles(get_settings(), "TCS", None)


def test_the_google_only_setting_never_calls_upstox(monkeypatch):
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "tok")
    monkeypatch.setenv("NEWS_SOURCE", "google")
    monkeypatch.setattr(upstox, "fetch_news", lambda *a: (_ for _ in ()).throw(AssertionError("Upstox was called")))
    monkeypatch.setattr(google_news, "fetch_news", lambda name, limit: [make_article("G", "u")])
    assert news_sources.collect_articles(get_settings(), "TCS", "NSE_EQ|X")[1] == "google"

from datetime import datetime, timedelta, timezone

import pytest

from app.integrations import finbert
from app.services import news, news_sources
from tests.helpers import fake_score_texts, make_article, make_sentiment


@pytest.fixture
def fakes(monkeypatch):
    """Two articles from a fake source, a fake model, and counters for how often each ran."""
    calls = {"collect": 0, "scored": 0}

    def fake_collect(settings, name, instrument_key):
        calls["collect"] += 1
        return [make_article("TCS up on deal", "https://x/1"), make_article("TCS down on probe", "https://x/2", "2026-10-09T09:00:00+00:00")], "google"

    def counting_score(texts, model_name):
        calls["scored"] += len(texts)
        return fake_score_texts(texts, model_name)

    monkeypatch.setattr(news_sources, "collect_articles", fake_collect)
    monkeypatch.setattr(finbert, "score_texts", counting_score)
    return calls


# ---------- fetching, scoring and caching ----------

def test_news_is_scored_once_then_served_from_cache(client, fakes):
    first = client.get("/stocks/TCS/news").json()
    assert first["from_cache"] is False and first["source"] == "google"
    assert first["summary"]["article_count"] == 2
    assert first["summary"]["counts"]["positive"] == 1 and first["summary"]["counts"]["negative"] == 1
    second = client.get("/stocks/tcs/news").json()  # lower case works too
    assert second["from_cache"] is True
    assert fakes["collect"] == 1 and fakes["scored"] == 2  # fetched and scored once only


def test_refresh_refetches_but_does_not_rescore_known_articles(client, fakes):
    client.get("/stocks/TCS/news")
    response = client.post("/stocks/TCS/refresh")
    assert response.status_code == 200 and response.json()["from_cache"] is False
    assert fakes["collect"] == 2
    assert fakes["scored"] == 2  # same URLs, so no re-scoring


def test_older_news_is_served_when_the_sources_fail(client, fakes, monkeypatch):
    client.get("/stocks/TCS/news")

    def sources_down(settings, name, instrument_key):
        raise news_sources.NewsUnavailableError("sources down")

    monkeypatch.setattr(news_sources, "collect_articles", sources_down)
    body = client.post("/stocks/TCS/refresh").json()
    assert body["stale"] is True and body["warning"] == "sources down" and len(body["articles"]) == 2


def test_503_when_sources_fail_and_nothing_is_cached(client, monkeypatch):
    def sources_down(settings, name, instrument_key):
        raise news_sources.NewsUnavailableError("sources down")

    monkeypatch.setattr(news_sources, "collect_articles", sources_down)
    response = client.get("/stocks/TCS/news")
    assert response.status_code == 503 and response.json()["detail"] == "sources down"


def test_only_one_fetch_happens_when_many_users_ask_at_once(client, fakes):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: client.get("/stocks/TCS/news"), range(8)))
    assert all(r.status_code == 200 for r in responses)
    assert fakes["collect"] == 1 and fakes["scored"] == 2


# ---------- the "last N days" window ----------

def test_window_filters_by_ist_calendar_day_and_resummarizes():
    now = datetime.now(timezone.utc)
    payload = {
        "articles": [
            {"title": "today", "published_at": now.isoformat(), "sentiment": make_sentiment("positive")},
            {"title": "five days ago", "published_at": (now - timedelta(days=5)).isoformat(), "sentiment": make_sentiment("negative")},
        ],
        "summary": {},
    }
    today_only = news.filter_to_last_days(payload, 1)
    assert [a["title"] for a in today_only["articles"]] == ["today"]
    assert today_only["summary"]["counts"] == {"positive": 1, "neutral": 0, "negative": 0} and today_only["window_days"] == 1
    assert len(news.filter_to_last_days(payload, 7)["articles"]) == 2
    assert news.filter_to_last_days(payload, None) is payload


def test_days_parameter_on_the_endpoint(client, monkeypatch):
    now = datetime.now(timezone.utc)
    articles = [
        make_article("fresh headline up", "https://x/1", now.isoformat()),
        make_article("old headline down", "https://x/2", (now - timedelta(days=4)).isoformat()),
    ]
    monkeypatch.setattr(news_sources, "collect_articles", lambda settings, name, key: (articles, "google"))
    monkeypatch.setattr(finbert, "score_texts", fake_score_texts)
    assert len(client.get("/stocks/TCS/news").json()["articles"]) == 2
    one_day = client.get("/stocks/TCS/news?days=1").json()
    assert [a["title"] for a in one_day["articles"]] == ["fresh headline up"] and one_day["window_days"] == 1
    assert one_day["summary"]["article_count"] == 1
    assert client.get("/stocks/TCS/news?days=0").status_code == 422
    assert client.get("/stocks/TCS/news?days=8").status_code == 422


# ---------- summary ----------

def test_summarize_sentiment():
    scored = [{"label": "positive", "compound": 0.9}, {"label": "positive", "compound": 0.5}, {"label": "negative", "compound": -0.2}]
    summary = news.summarize_sentiment(scored)
    assert summary["overall"] == "positive" and summary["counts"] == {"positive": 2, "neutral": 0, "negative": 1}
    assert news.summarize_sentiment([])["overall"] == "neutral"

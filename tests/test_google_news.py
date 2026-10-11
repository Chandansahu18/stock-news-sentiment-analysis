import pytest
import requests

from app.integrations import google_news, http
from tests.helpers import FakeResponse

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item><title>TCS wins big deal - Economic Times</title><link>https://n.example/1</link>
        <pubDate>Fri, 09 Oct 2026 10:00:00 GMT</pubDate><source url="https://et.example">Economic Times</source></item>
  <item><title>No date here - Mint</title><link>https://n.example/2</link><source>Mint</source></item>
  <item><title>TCS shares fall - Mint</title><link>https://n.example/3</link>
        <pubDate>Fri, 09 Oct 2026 12:00:00 GMT</pubDate><source>Mint</source></item>
</channel></rss>"""


def test_parses_cleans_titles_and_skips_undated_items(monkeypatch):
    monkeypatch.setattr(http, "get", lambda *a, **k: FakeResponse(content=RSS))
    items = google_news.fetch_news("Tata Consultancy Services", limit=10)
    assert [i["title"] for i in items] == ["TCS wins big deal", "TCS shares fall"]
    assert items[0]["source"] == "Economic Times"
    assert items[0]["published_at"].startswith("2026-10-09T10:00:00")


def test_respects_the_limit(monkeypatch):
    monkeypatch.setattr(http, "get", lambda *a, **k: FakeResponse(content=RSS))
    assert len(google_news.fetch_news("x", limit=1)) == 1


def test_network_error_becomes_a_safe_message(monkeypatch):
    def offline(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(http, "get", offline)
    with pytest.raises(google_news.GoogleNewsError):
        google_news.fetch_news("x")


def test_rejects_garbage_xml(monkeypatch):
    monkeypatch.setattr(http, "get", lambda *a, **k: FakeResponse(content=b"<html>not rss"))
    with pytest.raises(google_news.GoogleNewsError):
        google_news.fetch_news("x")

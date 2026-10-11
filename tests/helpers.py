"""Shared test data and fakes."""

from __future__ import annotations

import requests

FAKE_LISTING = {
    "equities": [
        {"symbol": "TCS", "name": "TCS", "key": "NSE_EQ|INE467B01029"},
        {"symbol": "INFY", "name": "Infosys", "key": "NSE_EQ|INE009A01021"},
        {"symbol": "RELIANCE", "name": "Reliance Industries", "key": "NSE_EQ|INE002A01018"},
        {"symbol": "M&M", "name": "Mahindra & Mahindra", "key": "NSE_EQ|INE101A01026"},
        {"symbol": "INFOBEAN", "name": "Infobeans Technologies", "key": "NSE_EQ|INE00BM01015"},
        {"symbol": "HDFCBANK", "name": "HDFC Bank", "key": "NSE_EQ|INE040A01034"},
    ],
    "fno_symbols": ["TCS", "INFY", "RELIANCE", "M&M", "HDFCBANK"],
}


class FakeResponse:
    """Just enough of requests.Response for the code under test."""

    def __init__(self, status_code=200, json_data=None, content=b"", headers=None):
        self.status_code = status_code
        self._json = json_data
        self.content = content
        self.headers = headers or {"content-type": "application/json"}

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def firewall_block_response() -> FakeResponse:
    """What Upstox's Cloudflare returns when it blocks us: HTML with a 403."""
    return FakeResponse(status_code=403, headers={"content-type": "text/html; charset=UTF-8"})


def make_article(title, url, published="2026-10-09T10:00:00+00:00", source="Test"):
    return {"title": title, "summary": "", "url": url, "source": source, "published_at": published}


def make_sentiment(label="positive"):
    positive = label == "positive"
    return {
        "label": label,
        "score": 0.9,
        "compound": 0.8 if positive else -0.8,
        "probs": {"positive": 0.9 if positive else 0.05, "neutral": 0.05, "negative": 0.05 if positive else 0.9},
    }


def fake_score_texts(texts, model_name):
    """Stands in for FinBERT: a headline containing 'up' is positive, anything else negative."""
    return [make_sentiment("positive" if "up" in text.lower() else "negative") for text in texts]

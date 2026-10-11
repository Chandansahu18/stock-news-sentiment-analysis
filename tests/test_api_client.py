import threading

import pytest
import requests

from tests.helpers import FakeResponse
from ui import api_client
from ui.api_client import ApiError


@pytest.fixture(autouse=True)
def fresh_cache():
    api_client.clear_cache()
    yield
    api_client.clear_cache()


def ok(data):
    return FakeResponse(json_data=data)


def test_stock_path_encodes_the_symbol():
    assert api_client.stock_path("TCS", "news") == "/stocks/TCS/news"
    assert api_client.stock_path("M&M", "news") == "/stocks/M%26M/news"
    assert api_client.stock_path("../x", "news") == "/stocks/..%2Fx/news"


def test_repeat_requests_are_answered_from_memory(monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "request", lambda method, url, params=None, timeout=None: calls.append(url) or ok({"n": 1}))
    assert api_client.get_cached("/stocks/top", mode="active") == {"n": 1}
    assert api_client.get_cached("/stocks/top", mode="active") == {"n": 1}
    api_client.get_cached("/stocks/top", mode="gainers")  # different parameters, different entry
    assert len(calls) == 2


def test_callers_get_private_copies(monkeypatch):
    monkeypatch.setattr(requests, "request", lambda *a, **k: ok({"items": [1]}))
    first = api_client.get_cached("/x")
    first["items"].append(99)
    assert api_client.get_cached("/x") == {"items": [1]}


def test_errors_are_not_cached(monkeypatch):
    answers = [FakeResponse(status_code=503, json_data={"detail": "down"}), ok({"fine": True})]
    monkeypatch.setattr(requests, "request", lambda *a, **k: answers.pop(0))
    with pytest.raises(ApiError, match="down"):
        api_client.get_cached("/x")
    assert api_client.get_cached("/x") == {"fine": True}  # the next call tries again


def test_unreachable_backend_explains_how_to_start_it(monkeypatch):
    def offline(*a, **k):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(requests, "request", offline)
    with pytest.raises(ApiError, match="uvicorn app.main:app"):
        api_client.get_cached("/x")


def test_the_cache_does_not_grow_without_limit(monkeypatch):
    monkeypatch.setattr(api_client, "MAX_CACHE_ENTRIES", 3)
    monkeypatch.setattr(requests, "request", lambda *a, **k: ok({}))
    for number in range(10):
        api_client.get_cached("/x", n=number)
    assert len(api_client._cache) <= 3


def test_calls_run_at_the_same_time_and_one_failure_does_not_hide_the_other(monkeypatch):
    barrier = threading.Barrier(2, timeout=3)  # only passes if both requests are in flight together

    def fake_request(method, url, params=None, timeout=None):
        barrier.wait()
        if url.endswith("/bad"):
            return FakeResponse(status_code=503, json_data={"detail": "nope"})
        return ok({"fine": True})

    monkeypatch.setattr(requests, "request", fake_request)
    results = api_client.fetch_concurrently({"a": ("/good", {}), "b": ("/bad", {})})
    assert results["a"] == {"fine": True}
    assert isinstance(results["b"], ApiError) and "nope" in str(results["b"])

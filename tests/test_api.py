import threading
import time

from app import warmup
from app.integrations import finbert, http
from app.services import stocks


def test_health_and_default_watchlist(client):
    assert client.get("/health").json() == {"status": "ok"}
    watchlist = client.get("/stocks").json()
    assert any(s["symbol"] == "TCS" for s in watchlist) and len(watchlist) >= 10


def test_unknown_and_invalid_symbols(client):
    assert client.get("/stocks/NOTREAL/news").status_code == 404
    assert client.get("/stocks/bad%20symbol!/news").status_code == 422
    assert client.get("/stocks/..%2F..%2Fetc/news").status_code in (404, 422)


def test_responses_are_compressed_when_the_client_accepts_it(client):
    response = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200 and response.headers.get("content-encoding") == "gzip"


# ---------- start-up warm-up ----------

def test_warmup_loads_the_stock_list_and_model_in_the_background(monkeypatch):
    monkeypatch.setenv("PRELOAD_ON_STARTUP", "true")
    loaded = []
    monkeypatch.setattr(stocks, "get_listing", lambda: loaded.append("listing"))
    monkeypatch.setattr(finbert, "load_model", lambda name: loaded.append("model"))
    for thread in warmup.start_background_warmup():
        thread.join(timeout=3)
    assert sorted(loaded) == ["listing", "model"]


def test_warmup_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("PRELOAD_ON_STARTUP", "false")
    assert warmup.start_background_warmup() == []


def test_a_failing_warmup_task_does_not_crash_anything(monkeypatch):
    monkeypatch.setenv("PRELOAD_ON_STARTUP", "true")

    def broken():
        raise RuntimeError("no network")

    monkeypatch.setattr(stocks, "get_listing", broken)
    monkeypatch.setattr(finbert, "load_model", lambda name: None)
    for thread in warmup.start_background_warmup():
        thread.join(timeout=3)  # completes without raising


# ---------- outbound HTTP safety ----------

def test_only_a_limited_number_of_outbound_requests_run_at_once(monkeypatch):
    running = 0
    peak = 0
    guard = threading.Lock()

    class FakeSession:
        def get(self, url, params=None, headers=None, timeout=None):
            nonlocal running, peak
            with guard:
                running += 1
                peak = max(peak, running)
            time.sleep(0.03)
            with guard:
                running -= 1

    monkeypatch.setattr(http, "_session", FakeSession())
    threads = [threading.Thread(target=http.get, args=("https://example.invalid",)) for _ in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert 1 < peak <= http.MAX_SIMULTANEOUS_REQUESTS


def test_firewall_and_rate_limit_responses_are_never_retried():
    retry = http._session.get_adapter("https://api.upstox.com").max_retries
    assert 403 not in retry.status_forcelist and 429 not in retry.status_forcelist
    assert set(retry.status_forcelist) == {502, 503, 504}

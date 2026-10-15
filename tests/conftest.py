import pytest
from fastapi.testclient import TestClient

from tests.helpers import FAKE_LISTING


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Every test gets an empty cache folder, no real credentials, no model preload and no network for the stock list."""
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "")
    monkeypatch.setenv("NEWS_TTL_MINUTES", "30")
    monkeypatch.setenv("PRELOAD_ON_STARTUP", "false")
    from app.integrations import nse_listing, upstox
    from app.services import stocks

    monkeypatch.setattr(nse_listing, "load_listing", lambda cache: FAKE_LISTING)
    stocks.clear_listing_memo()  # the stock list is remembered in memory; start every test without it
    upstox.reset_block()         # the firewall circuit breaker is process-wide state
    yield
    stocks.clear_listing_memo()
    upstox.reset_block()


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)

import pytest

from app.integrations import http, upstox
from tests.helpers import FakeResponse, firewall_block_response

KEY = "NSE_EQ|INE467B01029"


# ---------- candles, last price, news ----------

def test_candles_are_parsed_sorted_and_the_token_is_sent(monkeypatch):
    seen = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        seen.update(url=url, headers=headers)
        return FakeResponse(
            json_data={
                "status": "success",
                "data": {
                    "candles": [
                        ["2026-10-09T00:00:00+05:30", 102, 105, 101, 104, 5000, 0],
                        ["2026-10-08T00:00:00+05:30", 100, 103, 99, 102, 4000, 0],
                        ["bad row"],
                    ]
                },
            }
        )

    monkeypatch.setattr(http, "get", fake_get)
    candles = upstox.fetch_candles("SECRET-TOKEN", KEY, days=10)
    assert [c["date"] for c in candles] == ["2026-10-08", "2026-10-09"]
    assert candles[1]["close"] == 104.0
    assert "NSE_EQ%7CINE467B01029" in seen["url"] and "/days/1/" in seen["url"]
    assert seen["headers"]["Authorization"] == "Bearer SECRET-TOKEN"


def test_news_is_parsed(monkeypatch):
    body = {
        "status": "success",
        "data": {KEY: [{"heading": "TCS up", "summary": "s", "article_link": "https://u/1", "published_time": 1760000000000}, {"heading": "", "published_time": 1}]},
    }
    monkeypatch.setattr(http, "get", lambda *a, **k: FakeResponse(json_data=body))
    items = upstox.fetch_news("tok", KEY)
    assert len(items) == 1 and items[0]["title"] == "TCS up" and items[0]["source"] == "Upstox"
    assert items[0]["published_at"].endswith("+00:00")


def test_last_price(monkeypatch):
    body = {"status": "success", "data": {"NSE_EQ:TCS": {"last_price": 3999.5, "instrument_token": KEY}}}
    monkeypatch.setattr(http, "get", lambda *a, **k: FakeResponse(json_data=body))
    assert upstox.fetch_last_price("tok", KEY) == 3999.5


@pytest.mark.parametrize("status,fragment", [(401, "rejected"), (403, "rejected"), (429, "too many requests"), (500, "HTTP 500")])
def test_errors_never_leak_the_token(monkeypatch, status, fragment):
    monkeypatch.setattr(http, "get", lambda *a, **k: FakeResponse(status_code=status))
    with pytest.raises(upstox.UpstoxError) as exc:
        upstox.fetch_candles("SECRET-TOKEN", KEY)
    assert fragment in str(exc.value) and "SECRET-TOKEN" not in str(exc.value)


def test_a_token_is_required():
    with pytest.raises(upstox.UpstoxError):
        upstox.fetch_candles("", KEY)


# ---------- live quotes ----------

def _quote(symbol, price, net_change, volume, average=None, last_trade_time="1760000000000"):
    return {
        "symbol": symbol, "instrument_token": f"NSE_EQ|{symbol}", "last_price": price, "net_change": net_change,
        "volume": volume, "average_price": average, "last_trade_time": last_trade_time,
    }


def test_quotes_are_parsed_and_requested_in_batches(monkeypatch):
    batch_sizes = []

    def fake_get(url, params=None, headers=None, timeout=None):
        keys = params["instrument_key"].split(",")
        batch_sizes.append(len(keys))
        data = {f"NSE_EQ:{k}": _quote(k.split("|")[1], 110.0, 10.0, 1000, 105.0) for k in keys}
        data["NSE_EQ:BAD"] = {"symbol": "BAD", "last_price": None}
        return FakeResponse(json_data={"status": "success", "data": data})

    monkeypatch.setattr(http, "get", fake_get)
    monkeypatch.setattr(upstox.time, "sleep", lambda seconds: None)
    keys = [f"NSE_EQ|S{i}" for i in range(150)]
    quotes = upstox.fetch_quotes("tok", keys, batch_size=100)
    assert batch_sizes == [100, 50] and len(quotes) == 150  # two requests, malformed rows skipped
    first = quotes[0]
    assert first["change_pct"] == 10.0 and first["turnover"] == 105000.0  # 10/100, volume x average price
    assert first["session_date"] and first["key"] == "NSE_EQ|S0"


def test_turnover_uses_last_price_when_there_is_no_average(monkeypatch):
    body = {"status": "success", "data": {"NSE_EQ:A": _quote("A", 50.0, -5.0, 10, average=0)}}
    monkeypatch.setattr(http, "get", lambda *a, **k: FakeResponse(json_data=body))
    quote = upstox.fetch_quotes("tok", ["NSE_EQ|A"])[0]
    assert quote["turnover"] == 500.0 and quote["change_pct"] == -9.09


# ---------- firewall circuit breaker ----------

def test_cloudflare_block_page_is_not_reported_as_a_bad_token(monkeypatch):
    monkeypatch.setattr(http, "get", lambda *a, **k: firewall_block_response())
    with pytest.raises(upstox.UpstoxError) as exc:
        upstox.fetch_quotes("tok", ["NSE_EQ|A"])
    assert "temporarily blocking" in str(exc.value) and "token" not in str(exc.value).lower()


def test_after_a_block_no_requests_are_sent_until_the_cooldown_ends(monkeypatch):
    calls = []
    monkeypatch.setattr(http, "get", lambda *a, **k: calls.append(1) or firewall_block_response())
    for _ in range(4):  # one real request, then three stopped locally
        with pytest.raises(upstox.UpstoxError) as exc:
            upstox.fetch_last_price("tok", "NSE_EQ|A")
        assert "paused price requests until" in str(exc.value) and "IST" in str(exc.value)
    assert len(calls) == 1

    upstox._blocked_until = upstox.time.time() - 1  # the cooldown has passed
    ok = FakeResponse(json_data={"status": "success", "data": {"NSE_EQ:A": {"last_price": 5.0, "instrument_token": "NSE_EQ|A"}}})
    monkeypatch.setattr(http, "get", lambda *a, **k: calls.append(1) or ok)
    upstox.fetch_last_price("tok", "NSE_EQ|A")
    assert len(calls) == 2  # exactly one probe went out


def test_block_message_has_no_em_or_en_dashes(monkeypatch):
    monkeypatch.setattr(http, "get", lambda *a, **k: firewall_block_response())
    with pytest.raises(upstox.UpstoxError) as exc:
        upstox.fetch_news("tok", "NSE_EQ|A")
    assert "\u2014" not in str(exc.value) and "\u2013" not in str(exc.value)

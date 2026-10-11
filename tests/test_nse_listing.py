import requests

from app.cache import JsonFileCache
from app.integrations import nse_listing

ROWS = [
    {"segment": "NSE_EQ", "instrument_type": "EQ", "trading_symbol": "RELIANCE", "name": "RELIANCE INDUSTRIES LTD", "short_name": "Reliance Industries", "instrument_key": "NSE_EQ|INE002A01018"},
    {"segment": "NSE_EQ", "instrument_type": "EQ", "trading_symbol": "FOOBAR", "name": "FOO BAR LTD", "instrument_key": "NSE_EQ|INE000000001"},
    {"segment": "NSE_EQ", "instrument_type": "SM", "trading_symbol": "SMEONLY", "name": "SME CO", "instrument_key": "NSE_EQ|INE000000002"},
    {"segment": "NSE_EQ", "instrument_type": "EQ", "trading_symbol": "NOKEY", "name": "NO KEY LTD"},
    {"segment": "NSE_FO", "instrument_type": "FUT", "underlying_type": "EQUITY", "underlying_symbol": "RELIANCE"},
    {"segment": "NSE_FO", "instrument_type": "FUT", "underlying_type": "EQUITY", "underlying_symbol": "RELIANCE"},
    {"segment": "NSE_FO", "instrument_type": "FUT", "underlying_type": "INDEX", "underlying_symbol": "NIFTY"},
    {"segment": "NSE_FO", "instrument_type": "CE", "underlying_type": "EQUITY", "underlying_symbol": "FOOBAR"},
]

# The conftest replaces nse_listing.load_listing for every test; keep the real function to test it.
REAL_LOAD_LISTING = nse_listing.load_listing


def test_parse_keeps_main_board_equities_and_fno_stocks():
    listing = nse_listing.parse_listing(ROWS)
    by_symbol = {e["symbol"]: e for e in listing["equities"]}
    assert set(by_symbol) == {"RELIANCE", "FOOBAR"}  # SME and key-less rows dropped
    assert by_symbol["RELIANCE"]["name"] == "Reliance Industries"  # short_name preferred
    assert by_symbol["FOOBAR"]["name"] == "Foo Bar"  # upper-case legal name tidied, suffix removed
    assert listing["fno_symbols"] == ["RELIANCE"]  # futures only, equities only, de-duplicated


def test_load_uses_the_cache_and_survives_being_offline(tmp_path, monkeypatch):
    downloads = []
    monkeypatch.setattr(nse_listing, "download_rows", lambda: downloads.append(1) or ROWS)
    cache = JsonFileCache(tmp_path)
    assert REAL_LOAD_LISTING(cache)["fno_symbols"] == ["RELIANCE"]
    REAL_LOAD_LISTING(cache)
    assert len(downloads) == 1  # the second call came from the cache

    def offline():
        raise requests.ConnectionError("down")

    monkeypatch.setattr(nse_listing, "download_rows", offline)
    assert REAL_LOAD_LISTING(JsonFileCache(tmp_path / "empty")) == {}  # nothing cached and offline: empty, not a crash

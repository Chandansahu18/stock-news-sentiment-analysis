"""Offline, in-memory regression tests; examples never become project data."""

import csv
import hashlib
import io
import unittest
from unittest.mock import patch

from stock_sentiment.ingestion.watchlist import APPROVED_SYMBOLS, render_watchlist
from stock_sentiment.providers.nifty import (
    MAX_SOURCE_BYTES,
    download_constituents,
    parse_constituents,
)


def source_example(symbols=None):
    """Build a test-only CSV in memory, not a market-data output file."""
    symbols = symbols if symbols is not None else [
        *APPROVED_SYMBOLS, *(f"EXAMPLE{i}" for i in range(30))
    ]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["Company Name", "Industry", "Symbol", "Series", "ISIN Code"])
    for symbol in symbols:
        writer.writerow([f"{symbol} Example Ltd.", "Test only", symbol, "EQ", "TEST_ONLY"])
    return buffer.getvalue().encode("utf-8")


class ConstituentTests(unittest.TestCase):
    def test_parse_valid_export(self):
        rows = parse_constituents(source_example())
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[0].symbol, "RELIANCE")

    def test_accept_utf8_bom(self):
        self.assertEqual(len(parse_constituents(b"\xef\xbb\xbf" + source_example())), 50)

    def test_reject_html_instead_of_csv(self):
        with self.assertRaisesRegex(ValueError, "constituent columns"):
            parse_constituents(b"<html>Access denied</html>")

    def test_reject_partial_constituent_list(self):
        with self.assertRaisesRegex(ValueError, "Expected 50"):
            parse_constituents(source_example(list(APPROVED_SYMBOLS)))

    def test_reject_duplicate_symbols(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_constituents(source_example(["RELIANCE"] * 50))

    def test_reject_oversized_source(self):
        with self.assertRaisesRegex(ValueError, "1 MiB"):
            parse_constituents(b"x" * (MAX_SOURCE_BYTES + 1))

    def test_download_has_one_bounded_request(self):
        with patch("stock_sentiment.providers.nifty.build_opener") as factory:
            response = factory.return_value.open.return_value.__enter__.return_value
            response.read.return_value = source_example()
            snapshot = download_constituents()
            factory.return_value.open.assert_called_once()
            self.assertEqual(factory.return_value.open.call_args.kwargs["timeout"], 20)
            response.read.assert_called_once_with(MAX_SOURCE_BYTES + 1)
            self.assertEqual(snapshot.sha256, hashlib.sha256(snapshot.content).hexdigest())


class WatchlistTests(unittest.TestCase):
    def render(self, source=None, retrieved_at="2026-10-09T13:35:12+00:00"):
        source = source_example() if source is None else source
        return render_watchlist(
            source,
            source_sha256=hashlib.sha256(source).hexdigest(),
            retrieved_at=retrieved_at,
        )

    def test_generate_preserves_official_names_and_order(self):
        content, receipt = self.render()
        rows = list(csv.DictReader(io.StringIO(content)))
        self.assertEqual([row["symbol"] for row in rows], list(APPROVED_SYMBOLS))
        self.assertEqual(rows[0]["name"], "RELIANCE Example Ltd.")
        self.assertEqual(rows[0]["yahoo_ticker"], "RELIANCE.NS")
        self.assertEqual(rows[0]["news_query"], "RELIANCE Example stock")
        self.assertEqual(receipt["watchlist_count"], 20)
        self.assertEqual(receipt["source_constituent_count"], 50)
        self.assertEqual(receipt["watchlist_sha256"], hashlib.sha256(content.encode()).hexdigest())

    def test_preserve_ampersand_ticker(self):
        content, _ = self.render()
        rows = {row["symbol"]: row for row in csv.DictReader(io.StringIO(content))}
        self.assertEqual(rows["M&M"]["yahoo_ticker"], "M&M.NS")

    def test_reject_changed_source_hash(self):
        with self.assertRaisesRegex(ValueError, "hash"):
            render_watchlist(
                source_example(), source_sha256="0" * 64,
                retrieved_at="2026-10-09T13:35:12+00:00",
            )

    def test_reject_missing_approved_symbol(self):
        symbols = ["OTHER" if symbol == "TCS" else symbol for symbol in APPROVED_SYMBOLS]
        symbols.extend(f"EXAMPLE{i}" for i in range(30))
        with self.assertRaisesRegex(ValueError, "missing.*TCS"):
            self.render(source_example(symbols))

    def test_reject_naive_timestamp(self):
        with self.assertRaisesRegex(ValueError, "UTC"):
            self.render(retrieved_at="2026-10-09T13:35:12")

    def test_reject_non_utc_timestamp(self):
        with self.assertRaisesRegex(ValueError, "UTC"):
            self.render(retrieved_at="2026-10-09T19:05:12+05:30")


if __name__ == "__main__":
    unittest.main()

"""Generate an auditable watchlist from a separately approved official download."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from stock_sentiment.providers.nifty import (
    SOURCE_URL,
    download_constituents,
    parse_constituents,
)

# The user approved this demo subset. This is not a market-cap ranking.
APPROVED_SYMBOLS = (
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "ITC", "BHARTIARTL",
    "LT", "ADANIENT", "AXISBANK", "KOTAKBANK", "HINDUNILVR", "MARUTI", "M&M",
    "SUNPHARMA", "TITAN", "ULTRACEMCO", "NTPC", "POWERGRID",
)
WATCHLIST_COLUMNS = ("symbol", "name", "yahoo_ticker", "news_query")


def render_watchlist(
    source: bytes, *, source_sha256: str, retrieved_at: str
) -> tuple[str, dict]:
    """Return verified CSV text and provenance without I/O or synthetic fallbacks."""
    if hashlib.sha256(source).hexdigest() != source_sha256:
        raise ValueError("Source hash does not match the approved download receipt.")
    timestamp = datetime.fromisoformat(retrieved_at)
    if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("The retrieval timestamp must include the UTC timezone.")
    constituents = parse_constituents(source)
    by_symbol = {company.symbol: company for company in constituents}
    missing = sorted(set(APPROVED_SYMBOLS) - by_symbol.keys())
    if missing:
        raise ValueError(f"Approved symbols missing from the official source: {', '.join(missing)}")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=WATCHLIST_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for symbol in APPROVED_SYMBOLS:
        company = by_symbol[symbol]
        query_name = re.sub(r"\s+(?:Ltd\.?|Limited)$", "", company.name, flags=re.IGNORECASE)
        writer.writerow(
            {
                "symbol": company.symbol,
                "name": company.name,
                "yahoo_ticker": f"{company.symbol}.NS",
                "news_query": f"{query_name} stock",
            }
        )
    receipt = {
        "schema_version": 1,
        "source_url": SOURCE_URL,
        "retrieved_at_utc": timestamp.isoformat(),
        "source_sha256": source_sha256,
        "source_constituent_count": len(constituents),
        "watchlist_count": len(APPROVED_SYMBOLS),
        "watchlist_sha256": hashlib.sha256(buffer.getvalue().encode("utf-8")).hexdigest(),
        "selected_symbols": list(APPROVED_SYMBOLS),
        "selection_method": "User-approved 20-stock demo subset; not a market-cap ranking",
        "company_names": "Copied from the official source without modification",
        "yahoo_tickers": "Derived by appending .NS; live validation has not run",
        "news_queries": "Official company name without a trailing Ltd./Limited, followed by stock",
    }
    return buffer.getvalue(), receipt


def _atomic_write(destination: Path, content: bytes) -> None:
    """Keep partially written content out of the destination path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(content)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    download = commands.add_parser("download", help="Requires a separate source-download approval")
    download.add_argument(
        "--destination", type=Path, default=Path("data/runtime/nifty50-source.csv")
    )
    generate = commands.add_parser("generate", help="Requires a separate CSV-generation approval")
    generate.add_argument("--source", type=Path, default=Path("data/runtime/nifty50-source.csv"))
    generate.add_argument("--destination", type=Path, default=Path("data/watchlist.csv"))
    generate.add_argument("--receipt", type=Path, default=Path("data/watchlist.source.json"))
    generate.add_argument("--source-sha256", required=True)
    generate.add_argument("--retrieved-at", required=True)
    args = parser.parse_args()
    try:
        if args.operation == "download":
            if args.destination.exists():
                raise ValueError(
                    "Source file already exists. Review it before another approved download."
                )
            snapshot = download_constituents()
            _atomic_write(args.destination, snapshot.content)
            print(json.dumps({
                "source_url": SOURCE_URL,
                "retrieved_at_utc": snapshot.retrieved_at.isoformat(),
                "sha256": snapshot.sha256,
            }, indent=2))
        else:
            if args.destination == args.receipt:
                raise ValueError("Watchlist and receipt need different destination paths.")
            if args.destination.exists() or args.receipt.exists():
                raise ValueError(
                    "Watchlist or receipt already exists. Review before another generation."
                )
            content, receipt = render_watchlist(
                args.source.read_bytes(),
                source_sha256=args.source_sha256,
                retrieved_at=args.retrieved_at,
            )
            _atomic_write(args.receipt, (json.dumps(receipt, indent=2) + "\n").encode("utf-8"))
            _atomic_write(args.destination, content.encode("utf-8"))
            print(f"Created {receipt['watchlist_count']} official-source watchlist rows.")
    except (OSError, ValueError) as error:
        parser.exit(1, f"Watchlist operation failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

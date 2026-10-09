"""Read the official Nifty 50 export without scraping unstable HTML tables."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.request import HTTPRedirectHandler, Request, build_opener

SOURCE_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv"
MAX_SOURCE_BYTES = 1024 * 1024
REQUIRED_COLUMNS = frozenset({"Company Name", "Symbol", "Industry", "Series", "ISIN Code"})


@dataclass(frozen=True)
class Constituent:
    """Company metadata copied from an official constituent row."""

    symbol: str
    name: str


@dataclass(frozen=True)
class SourceDownload:
    """Validated source bytes and the actual retrieval receipt."""

    content: bytes
    retrieved_at: datetime
    sha256: str


def parse_constituents(payload: bytes) -> tuple[Constituent, ...]:
    """Reject malformed exports instead of creating a partial stock universe."""
    if len(payload) > MAX_SOURCE_BYTES:
        raise ValueError("Official source exceeds the 1 MiB limit.")
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    if not REQUIRED_COLUMNS.issubset(reader.fieldnames or []):
        raise ValueError("Response does not contain the official constituent columns.")
    constituents: list[Constituent] = []
    seen: set[str] = set()
    for row in reader:
        if None in row or any(row.get(column) is None for column in REQUIRED_COLUMNS):
            raise ValueError("Official source contains a malformed CSV row.")
        symbol = row["Symbol"].strip()
        name = row["Company Name"].strip()
        if not symbol or not name or symbol in seen:
            raise ValueError("Official source contains empty or duplicate company metadata.")
        if row["Series"].strip() != "EQ":
            raise ValueError(f"Unexpected trading series for {symbol}.")
        seen.add(symbol)
        constituents.append(Constituent(symbol=symbol, name=name))
    if len(constituents) != 50:
        raise ValueError(f"Expected 50 official constituents; received {len(constituents)}.")
    return tuple(constituents)


class _NoRedirect(HTTPRedirectHandler):
    """A source redirect needs review; do not silently request a different source."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download_constituents() -> SourceDownload:
    """Make one bounded request. Call only after a new download approval."""
    request = Request(
        SOURCE_URL,
        headers={
            "User-Agent": "stock-sentiment/0.1 official-constituent-import",
            "Accept": "text/csv",
        },
    )
    with build_opener(_NoRedirect).open(request, timeout=20) as response:
        payload = response.read(MAX_SOURCE_BYTES + 1)
    parse_constituents(payload)
    return SourceDownload(
        content=payload,
        retrieved_at=datetime.now(UTC),
        sha256=hashlib.sha256(payload).hexdigest(),
    )

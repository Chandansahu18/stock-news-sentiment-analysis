"""Time helpers.

The Indian market runs on IST, so "today" always means the IST calendar day, whatever the
timezone of the machine running the server.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def today_ist() -> date:
    return datetime.now(IST).date()


def today_ist_iso() -> str:
    """Today's IST date as 'YYYY-MM-DD'."""
    return today_ist().isoformat()


def now_utc_iso() -> str:
    """Current moment as an ISO-8601 UTC timestamp (what we store in cached payloads)."""
    return datetime.now(timezone.utc).isoformat()

"""Number and time formatting for display."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def format_rupees(amount: float, decimals: int = 2) -> str:
    """Rupees with Indian digit grouping: 123456.5 -> ₹1,23,456.50"""
    negative = amount < 0
    whole, _, fraction = f"{abs(amount):.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, last_three = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [last_three])
    text = "₹" + whole + (f".{fraction}" if fraction else "")
    return f"-{text}" if negative else text


def format_signed(value: float, decimals: int = 2) -> str:
    """+80.00 / -7.70 / 0.00"""
    return f"{value:+,.{decimals}f}" if value else f"{0:.{decimals}f}"


def format_day(iso_date: str | None) -> str:
    """'2026-10-09' -> '09 Oct' (empty text if missing or malformed)."""
    try:
        return f"{datetime.fromisoformat(str(iso_date)):%d %b}"
    except ValueError:
        return ""


def format_timestamp(iso_timestamp: str) -> str:
    """ISO timestamp -> '09 Oct, 8:41 PM IST' (the raw text if it cannot be read)."""
    try:
        moment = datetime.fromisoformat(iso_timestamp).astimezone(IST)
    except (ValueError, TypeError):
        return str(iso_timestamp)
    hour = moment.hour % 12 or 12
    return f"{moment:%d %b}, {hour}:{moment:%M} {moment:%p} IST"

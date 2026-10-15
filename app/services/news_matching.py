"""Which names a stock goes by in headlines, and whether a headline is really about it.

Google News matches words anywhere in an article, so searching for one company can also return stories that
only mention it deep in the text, or not at all (an RBI rupee story came back for HPCL). So we search for every
common name of the stock, then keep only the headlines that contain one of those names.

Names come from three places:
  * the company name, without a trailing Corp / Ltd / Limited ("Hindustan Petroleum Corp" -> "Hindustan Petroleum");
  * the ticker, and an acronym of the name ("Hindustan Petroleum Corp" -> "HPCL", which is what media write);
  * `stock_aliases.json`, for names that cannot be worked out ("HUL", "L&T", "SBI").
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache

from app.config import ALIASES_PATH

GENERIC_ENDINGS = {"corp", "corporation", "co", "company", "ltd", "limited"}
ACRONYM_SKIP_WORDS = {"of", "and", "the", "&"}
MIN_TICKER_LENGTH = 3    # shorter tickers ("LT", "IT") are ordinary words in headlines
MIN_ACRONYM_LENGTH = 4   # "HPCL" is distinctive; a 3-letter guess like "HPC" is not


@lru_cache(maxsize=1)
def _curated_aliases() -> dict[str, tuple[str, ...]]:
    with open(ALIASES_PATH, encoding="utf-8") as handle:
        return {symbol: tuple(names) for symbol, names in json.load(handle).items()}


def _without_generic_endings(name: str) -> str:
    words = name.split()
    while len(words) > 1 and words[-1].lower().strip(".") in GENERIC_ENDINGS:
        words.pop()
    return " ".join(words)


def _acronyms(name: str) -> list[str]:
    """Initials of the name's words, plus the same with a trailing L (for "Limited"), when long enough to be distinctive."""
    initials = "".join(
        word[0] for word in name.replace("&", " ").split() if word.lower() not in ACRONYM_SKIP_WORDS and word[0].isalpha()
    ).upper()
    if len(name.split()) < 2:
        return []
    return [variant for variant in (initials, initials + "L") if len(variant) >= MIN_ACRONYM_LENGTH]


def aliases_for(stock: dict) -> list[str]:
    """Every name headlines may use for this stock, most specific first. `stock` has "symbol" and "name"."""
    name, symbol = stock["name"].strip(), stock["symbol"]
    candidates = [_without_generic_endings(name)]
    if re.fullmatch(r"[A-Z0-9&]+", symbol) and len(symbol) >= MIN_TICKER_LENGTH:
        candidates.append(symbol)
    candidates += _acronyms(name)
    candidates += _curated_aliases().get(symbol, ())

    aliases: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip().replace("\u2019", "'")
        if candidate and candidate.lower() not in seen:
            seen.add(candidate.lower())
            aliases.append(candidate)
    return aliases


def _alias_pattern(alias: str) -> str:
    body = r"\s+".join(re.escape(part) for part in alias.split())
    # Tickers and acronyms must match in capitals ("OIL" is Oil India, "oil" is just oil). Names ignore case.
    is_acronym = alias.isupper() and " " not in alias
    return body if is_acronym else f"(?i:{body})"


def headline_matcher(aliases: list[str]) -> Callable[[str], bool]:
    """A function that says whether a headline contains one of the aliases as a whole word."""
    pattern = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(_alias_pattern(alias) for alias in aliases) + r")(?![A-Za-z0-9])")
    return lambda headline: bool(pattern.search(headline.replace("\u2019", "'")))

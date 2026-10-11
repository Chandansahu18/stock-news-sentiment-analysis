"""Response models. They define the API contract (and the OpenAPI docs at /docs).

Field names such as `compound` and `probs` are kept as they are on purpose: they are also stored in the
cache files and read by the dashboard, so renaming them would break both.
"""

from __future__ import annotations

from pydantic import BaseModel


class Stock(BaseModel):
    symbol: str
    name: str


class SentimentProbabilities(BaseModel):
    positive: float
    neutral: float
    negative: float


class ArticleSentiment(BaseModel):
    label: str                      # positive | neutral | negative
    score: float                    # probability of that label
    compound: float                 # positive minus negative probability, -1 to +1
    probs: SentimentProbabilities


class Article(BaseModel):
    title: str
    summary: str = ""
    url: str = ""
    source: str = ""
    published_at: str
    sentiment: ArticleSentiment


class SentimentSummary(BaseModel):
    overall: str
    average_score: float
    article_count: int
    counts: dict[str, int]


class NewsResponse(BaseModel):
    symbol: str
    name: str
    source: str
    fetched_at: str
    summary: SentimentSummary
    articles: list[Article]
    from_cache: bool
    stale: bool                     # True when a refresh failed and older data is shown
    warning: str | None = None
    window_days: int | None = None  # set when the request limited the news to the last N days


class RankedStock(BaseModel):
    symbol: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    turnover: int | None = None


class TopStocksResponse(BaseModel):
    mode: str
    date: str
    session_date: str | None = None  # the trading day the prices belong to
    as_of: str
    universe: int                    # how many stocks were ranked
    fallback: bool                   # True when this is the default watchlist, not a live ranking
    stale: bool
    warning: str | None = None
    stocks: list[RankedStock]


class Candle(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceResponse(BaseModel):
    symbol: str
    name: str
    currency: str
    price: float
    previous_close: float
    change: float
    change_pct: float
    as_of: str
    candles: list[Candle]
    stale: bool
    warning: str | None = None

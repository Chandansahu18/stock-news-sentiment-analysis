"""HTTP endpoints. Each one only validates input and calls a service; errors are mapped in error_handlers.py."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query

from app.services import news, prices, stocks, top_stocks
from .schemas import NewsResponse, PriceResponse, Stock, TopStocksResponse

router = APIRouter()

SymbolPath = Annotated[str, Path(pattern=r"^[A-Za-z0-9&-]{1,20}$", description="NSE trading symbol, e.g. TCS")]
NewsDays = Annotated[int | None, Query(ge=1, le=7, description="Keep only the last N days of news (1 = today)")]


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/stocks", response_model=list[Stock])
def default_watchlist():
    """The default watchlist (shown when live rankings are unavailable)."""
    return stocks.default_watchlist()


@router.get("/stocks/search", response_model=list[Stock])
def search_stocks(
    q: Annotated[str, Query(min_length=1, max_length=40, description="Company name or symbol")],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
):
    """Search every NSE equity by symbol or company name, best matches first."""
    return stocks.search_stocks(q, limit)


@router.get("/stocks/top", response_model=TopStocksResponse)
def top_stocks_today(mode: Literal["active", "gainers", "losers"] = "active"):
    """Today's top 10 to 20 F&O stocks: most active by traded value, top gainers, or top losers."""
    return top_stocks.get_top_stocks(mode)


@router.get("/stocks/{symbol}/news", response_model=NewsResponse)
def stock_news(symbol: SymbolPath, days: NewsDays = None):
    """News with FinBERT sentiment. Served from cache while fresh (30 minutes by default)."""
    return news.get_news(symbol, refresh=False, days=days)


@router.post("/stocks/{symbol}/refresh", response_model=NewsResponse)
def refresh_stock_news(symbol: SymbolPath, days: NewsDays = None):
    """Force a re-fetch of the news for one stock. Articles scored before are not scored again."""
    return news.get_news(symbol, refresh=True, days=days)


@router.get("/stocks/{symbol}/prices", response_model=PriceResponse)
def stock_prices(symbol: SymbolPath, days: Annotated[int, Query(ge=5, le=365)] = 30):
    """Daily candles and the latest price, from Upstox."""
    return prices.get_prices(symbol, days)

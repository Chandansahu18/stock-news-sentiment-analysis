# Indian Stock News Sentiment

Shows today's most active NSE stocks (or any stock you search for) with their price and the news of the
day, each headline scored by **FinBERT** (BERT trained on financial text). A **FastAPI** backend does the
work and a **Streamlit** dashboard shows it. No database: results are cached as JSON files.

> For information only. Sentiment scores are model output on headlines, not investment advice.

## How it works

```
 Dashboard (Streamlit)  ──HTTP──>  API (FastAPI)  ──>  services  ──>  integrations  ──>  Upstox / Google News / FinBERT
   ui/ + dashboard.py              app/api/            app/services/   app/integrations/
                                                            │
                                                            └──>  cache (app/cache.py, JSON files)
```

Each layer only talks to the one below it:

| Layer | Folder | Job |
|---|---|---|
| Dashboard | `dashboard.py`, `ui/` | Draws the page. Reaches the backend only through `ui/api_client.py`. |
| API | `app/api/`, `app/main.py` | Validates requests, shapes responses, maps errors to HTTP codes. No business logic. |
| Services | `app/services/` | One module per use-case: `stocks` (directory and search), `top_stocks`, `news`, `news_sources`, `news_matching`, `prices`. |
| Integrations | `app/integrations/` | The outside world: `upstox`, `google_news`, `nse_listing`, `finbert`, and the shared `http` session. |
| Cache | `app/cache.py` | The only code that touches disk. Replace `JsonFileCache` to move to PostgreSQL later. |

Small shared helpers: `config.py` (settings), `errors.py`, `clock.py` (IST dates), `concurrency.py` (one lock per stock), `warmup.py` (background start-up loading).

| Part | Choice | Why |
|---|---|---|
| Prices | Upstox API (Analytics Token) | Official broker data for NSE |
| News | Google News RSS | No key needed, covers Indian companies. Searched by every name the stock goes by (for example "Hindustan Petroleum" and "HPCL"), then only headlines that contain one of those names are kept. |
| Sentiment | `ProsusAI/finbert` (Hugging Face) | Pretrained on finance text, runs locally, no training needed |
| Storage | JSON files with expiry, behind `app/cache.py` | Scoring is the slow step, so results are cached. It is a cache, not a store of record. |
| API | FastAPI | Auto docs at `/docs`, request validation |
| UI | Streamlit | Python-only dashboard. It only calls the API, so React could replace it later. |

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # then edit .env and paste your Analytics Token
```

Get the token from your app at https://account.upstox.com/developer/apps (Analytics Token,
read-only, valid 1 year). Put it in `.env` only. Never commit `.env` or paste the token in chat or screenshots.

Without a token the app still works for news (Google News RSS), but prices and live rankings are unavailable.

## Run

Two terminals, both from the project folder with the venv active:

```powershell
# 1) API  (http://127.0.0.1:8010/docs for interactive docs)
uvicorn app.main:app --host 127.0.0.1 --port 8010

# 2) Dashboard  (http://localhost:8501)
streamlit run dashboard.py
```

The very first run downloads the FinBERT model (about 440 MB, once). After that, the API loads the model and the
stock list in the background at start-up, so open the dashboard a few seconds after starting the API.

## Speed and load

What keeps the dashboard quick without hammering the data providers:

- **Warm start.** FinBERT and the NSE stock list load in the background when the API starts (`PRELOAD_ON_STARTUP`).
- **Cache first.** Scored news is cached for 30 minutes, prices for 5, the daily ranking for 20. Articles that were scored before are never scored again.
- **One fetch per stock.** If several users open the same stock together, one fetches and the rest wait for that result.
- **Parallel where it helps.** The price and the news load at the same time, and the two Upstox price calls run together. Loading placeholders are on screen from the start.
- **Gentle on providers.** One pooled connection session, at most 6 requests in flight, short retries for temporary 502/503/504 errors only (never for 403 or 429), and a 5 minute pause on all Upstox calls if its firewall blocks a request.
- **Smaller responses.** The API compresses JSON (one news response went from 16.5 KB to 8.6 KB).

Measured on this machine (Google News as the source, no Upstox token, so no price calls):

| Step | Without warm start | With warm start |
|---|---|---|
| First search | 3.1 s | 23 ms |
| News for the first stock | 13.9 s | 1.9 s |
| News for another new stock | 1.3 s | 0.9 s |
| News already cached | 13 ms | 15 ms |

In a real browser (Edge, warm API): the page title appeared after 1.2 s, the first stock's articles after 3.1 s, switching to a
new stock took 1.8 s, and switching back to a stock seen a moment before took 0.5 s. Times depend on your network and on Google.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/stocks` | Default watchlist (used when live rankings are unavailable) |
| GET | `/stocks/search?q=infos` | Search all ~2,700 NSE equities by symbol or company name |
| GET | `/stocks/top?mode=active` | Today's top 10 to 20 stocks: `active` (traded value), `gainers`, `losers` |
| GET | `/stocks/{symbol}/news?days=1` | Articles, sentiment and summary (cached 30 min). `days` 1-7 keeps only the last N days (1 = today) |
| POST | `/stocks/{symbol}/refresh` | Force a re-fetch (articles scored before are not scored again) |
| GET | `/stocks/{symbol}/prices?days=30` | Daily candles and latest price (needs the token) |

If the news sources are down, the last cached result is returned with `"stale": true`.

## Today's stocks and search

- **Search** covers every NSE main-board equity, from Upstox's public instruments file (no token needed). Matches are ranked: exact symbol, symbol prefix, name prefix, then partial matches.
- **Today's list** is built once per IST day (re-ranked every 20 minutes) from live Upstox quotes for the ~210 F&O stocks, the most liquid and most covered names. Lists: most active by traded value (volume x average price), top gainers, top losers. On weekends and holidays it shows the last trading session and says so.
- If live quotes are unavailable (no token, or Upstox blocks the request), the page falls back to the default watchlist and explains why.
- **News window:** the dashboard asks for today's news first. If nothing is dated today it shows the past 7 days and says so.
- BSE-only stocks are not included.

## Configuration (`.env`)

See `.env.example` for every setting. Main ones: `UPSTOX_ANALYTICS_TOKEN` (prices and rankings only),
`NEWS_TTL_MINUTES`, `PRICE_TTL_MINUTES`, `MAX_ARTICLES`, `TOP_STOCKS_COUNT`, `TOP_STOCKS_TTL_MINUTES`,
`PRELOAD_ON_STARTUP`, `API_BASE_URL`. `watchlist.json` holds the default watchlist and the preferred company names. `stock_aliases.json` lists extra names that headlines use for a stock when they cannot be worked out from its name or ticker (for example `"HINDUNILVR": ["HUL"]`); add a line there if a stock's news looks thin.

## Tests

```powershell
pytest
```

157 tests. All network calls and the model are mocked, so they run offline in a few seconds. They cover each module,
the API, the dashboard (with Streamlit's test runner), accessibility contrast of the real theme, and that the
price/news requests really run at the same time.

## Dashboard design

Built on Streamlit with a custom theme. The rules it follows:

- **Type:** Geist (variable, self-hosted from `static/`, SIL OFL license included), tabular figures for all numbers.
- **Colour:** neutral greys, one cobalt accent. Green, red and grey are used only for sentiment and price direction. Light and dark themes both work.
- **Never colour alone:** each sentiment has a text label and its own shape (up triangle, down triangle, dash). Candles are hollow when up and filled when down.
- **Layout:** controls on top (no sidebar), one centred column up to 1180 px, ruled article rows instead of cards, single column on phones.
- **States:** loading placeholders while data loads, plain-language empty and error notices, no spinners.
- **Accessibility:** WCAG AA contrast (checked in tests), visible focus rings, reduced motion respected, article text and URLs escaped before rendering.

Where things live: `.streamlit/config.toml` (theme and font), `ui/theme.py` and `ui/styles.css` (colours and layout), `ui/components.py` (HTML pieces),
`ui/charts.py` (price chart), `ui/sections/` (one module per block of the page), `dashboard.py` (puts the blocks together).
After changing `config.toml`, restart Streamlit (theme settings are read at start-up).

## Known limitations

- **No authentication or rate limiting on the API.** Keep it bound to `127.0.0.1`. Add authentication before exposing it anywhere.
- Upstox price and ranking calls are covered by mocked tests. The ranking call (`/v2/market-quote/quotes`) has not been verified against live Upstox yet, because Upstox's firewall (Cloudflare) was blocking this machine when it was built. Check it with your token once the block clears.
- FinBERT works on headlines and can misjudge some of them (for example dividend news scored negative). Google News results can include non-news pages, which are scored neutral.
- A headline is linked to a stock only if the headline itself contains one of the stock's names (company name, ticker, an acronym such as HPCL, or an entry in `stock_aliases.json`). Google also matches words buried in the article body, so without this check unrelated stories (an RBI rupee story under HPCL) slipped in. The price of this strictness: a story about "oil marketing companies" that never names the stock is left out, and a quiet stock may show few headlines. Roundup headlines that name several companies count toward each of them. Tickers that are also ordinary words (for example `OIL`, `ITC` for Input Tax Credit) can still let a few off-topic headlines through.
- The daily ranking covers F&O stocks only (about 210), not all 2,700 listed names. There is no history or trend: the cache only holds the latest fetch.
- The 5 minute Upstox pause is kept in memory, so restarting the API clears it.
- Port 8010 is used because 8000 is commonly taken (for example by Docker).

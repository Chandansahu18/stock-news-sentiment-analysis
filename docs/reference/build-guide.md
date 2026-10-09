# Indian Stock News Sentiment Demo: Step-by-Step Build Guide

*Goal: a FastAPI service + dashboard that shows Indian (NSE) stock prices, live news per stock, and FinBERT sentiment (positive / negative / neutral) for each headline. Deadline: tomorrow noon.*

## 0. Decisions locked in (don't revisit)

| Layer | Choice | Why |
| --- | --- | --- |
| Prices | `yfinance` with `.NS` tickers | Free, no key. Unofficial and can be delayed, so we cache and mark stale data |
| News | Google News RSS (`en-IN`) per company | Free, no key, India-focused. Finnhub is weak on Indian stocks, so skip it |
| Sentiment | `ProsusAI/finbert`, baked into the Docker image | Finance-trained; no download at demo time |
| Backend | FastAPI + SQLAlchemy + Pydantic | Industry standard, auto Swagger docs |
| DB | PostgreSQL 16 | Real DB, not a toy |
| Scheduler | APScheduler in a separate `worker` container | Keeps ingestion out of the API process |
| Dashboard | Streamlit calling the API | Fastest path to a clean UI |
| Packaging | Docker Compose (db, init, api, worker, dashboard) | One command to run everything |

**Scope rule:** "all stocks" is impossible on free sources. Build for the **Nifty 50 (start with 20)**, driven by one CSV, so adding stocks is a config change, not a code change. State this openly in the demo.

## 1. Project structure

```
stock-sentiment/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env
├── data/watchlist.csv
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── schemas.py
│   ├── sentiment.py
│   ├── news.py
│   ├── prices.py
│   ├── seed.py
│   ├── worker.py
│   └── main.py
├── dashboard/app.py
├── scripts/verify_tickers.py
└── tests/test_basic.py
```

## 2. Step 1: Environment and watchlist (1 hr)

`requirements.txt`:

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
pydantic-settings==2.5.2
yfinance
feedparser==6.0.11
apscheduler==3.10.4
transformers==4.44.2
streamlit==1.38.0
streamlit-autorefresh==1.0.1
plotly==5.24.1
requests==2.32.3
pandas
pytest==8.3.3
httpx==0.27.2
```

Install CPU-only PyTorch first: `pip install torch --index-url https://download.pytorch.org/whl/cpu`

`data/watchlist.csv` (extend to 20 stocks the same way):

```
symbol,name,yahoo_ticker,news_query
RELIANCE,Reliance Industries,RELIANCE.NS,"\"Reliance Industries\" share"
TCS,Tata Consultancy Services,TCS.NS,"\"TCS\" Tata Consultancy share"
HDFCBANK,HDFC Bank,HDFCBANK.NS,"\"HDFC Bank\" share"
INFY,Infosys,INFY.NS,"\"Infosys\" share"
ICICIBANK,ICICI Bank,ICICIBANK.NS,"\"ICICI Bank\" share"
SBIN,State Bank of India,SBIN.NS,"\"SBI\" State Bank of India share"
ITC,ITC Limited,ITC.NS,"\"ITC\" share FMCG"
BHARTIARTL,Bharti Airtel,BHARTIARTL.NS,"\"Bharti Airtel\" share"
LT,Larsen & Toubro,LT.NS,"\"Larsen & Toubro\" share"
ADANIENT,Adani Enterprises,ADANIENT.NS,"\"Adani Enterprises\" share"
```

**Checkpoint (do this before anything else):** `scripts/verify_tickers.py` confirms every ticker actually returns data. Drop any that fail. Tickers change after mergers and demergers, so never assume.

```python
import pandas as pd, yfinance as yf
df = pd.read_csv("data/watchlist.csv")
for t in df.yahoo_ticker:
    h = yf.Ticker(t).history(period="5d")
    print(t, "OK" if not h.empty else "FAIL")
```

## 3. Step 2: Core backend code (2 hrs)

`app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://app:app@localhost:5432/stocks"
    news_interval_min: int = 10
    price_interval_min: int = 2
    api_url: str = "http://localhost:8000"
    model_config = {"env_file": ".env"}

settings = Settings()
```

`app/db.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`app/models.py` (store everything in UTC, convert to IST only in the UI)

```python
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def utcnow():
    return datetime.now(timezone.utc)

class Stock(Base):
    __tablename__ = "stocks"
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    yahoo_ticker: Mapped[str] = mapped_column(String(30))
    news_query: Mapped[str] = mapped_column(String(200))

class News(Base):
    __tablename__ = "news"
    __table_args__ = (UniqueConstraint("symbol", "url_hash"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("stocks.symbol"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2000))
    url_hash: Mapped[str] = mapped_column(String(64))
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sentiment: Mapped[str] = mapped_column(String(10), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    compound: Mapped[float] = mapped_column(Float)  # p(positive) - p(negative)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Price(Base):
    __tablename__ = "prices"
    symbol: Mapped[str] = mapped_column(ForeignKey("stocks.symbol"), primary_key=True)
    price: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

`app/sentiment.py` (model loads once, scoring is batched)

```python
from functools import lru_cache
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL = "ProsusAI/finbert"

@lru_cache(maxsize=1)
def _load():
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL).eval()
    return tok, model

def score_batch(texts, batch_size=16):
    tok, model = _load()
    labels = [model.config.id2label[i].lower() for i in range(model.config.num_labels)]
    pos, neg = labels.index("positive"), labels.index("negative")
    out = []
    for i in range(0, len(texts), batch_size):
        enc = tok(texts[i:i + batch_size], padding=True, truncation=True,
                  max_length=96, return_tensors="pt")
        with torch.no_grad():
            probs = torch.softmax(model(**enc).logits, dim=-1)
        for p in probs:
            k = int(p.argmax())
            out.append({"label": labels[k], "confidence": float(p[k]),
                        "compound": float(p[pos] - p[neg])})
    return out
```

`app/news.py`

```python
import calendar, hashlib, time, urllib.parse, logging
from datetime import datetime, timezone
import feedparser
from sqlalchemy.exc import IntegrityError
from .models import News, Stock
from .sentiment import score_batch

log = logging.getLogger(__name__)

def _feed_url(query):
    q = urllib.parse.quote_plus(f"{query} when:2d")
    return f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"

def fetch_news(query, limit=15):
    feed = feedparser.parse(_feed_url(query))
    items = []
    for e in feed.entries[:limit]:
        if getattr(e, "published_parsed", None):
            pub = datetime.fromtimestamp(calendar.timegm(e.published_parsed), tz=timezone.utc)
        else:
            pub = datetime.now(timezone.utc)
        title = e.title.rsplit(" - ", 1)[0].strip()
        src = e.get("source", {}).get("title") if hasattr(e, "get") else None
        items.append({"title": title[:500], "url": e.link[:2000], "source": src,
                      "published_at": pub,
                      "url_hash": hashlib.sha256(e.link.encode()).hexdigest()})
    return items

def ingest_stock(db, stock: Stock):
    items = fetch_news(stock.news_query)
    if not items:
        return 0
    hashes = [i["url_hash"] for i in items]
    existing = {h for (h,) in db.query(News.url_hash)
                .filter(News.symbol == stock.symbol, News.url_hash.in_(hashes))}
    fresh = [i for i in items if i["url_hash"] not in existing]
    if not fresh:
        return 0
    scores = score_batch([i["title"] for i in fresh])
    for i, s in zip(fresh, scores):
        db.add(News(symbol=stock.symbol, sentiment=s["label"],
                    confidence=s["confidence"], compound=s["compound"], **i))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return 0
    return len(fresh)

def ingest_all(db):
    total = 0
    for stock in db.query(Stock).all():
        try:
            total += ingest_stock(db, stock)
        except Exception:
            db.rollback()
            log.exception("news ingest failed for %s", stock.symbol)
        time.sleep(0.7)  # be polite, avoid being blocked
    log.info("news ingest done, %d new items", total)
```

`app/prices.py` (one batched call, failures never wipe old data)

```python
import logging
import yfinance as yf
from .models import Price, Stock, utcnow

log = logging.getLogger(__name__)

def refresh_prices(db):
    stocks = db.query(Stock).all()
    tickers = [s.yahoo_ticker for s in stocks]
    try:
        df = yf.download(tickers, period="5d", interval="1d",
                         group_by="ticker", progress=False, threads=True)
    except Exception:
        log.exception("price download failed; keeping previous prices")
        return
    for s in stocks:
        try:
            closes = df[s.yahoo_ticker]["Close"].dropna()
            if len(closes) < 2:
                continue
            price, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
            db.merge(Price(symbol=s.symbol, price=round(price, 2),
                           change_pct=round((price - prev) / prev * 100, 2),
                           updated_at=utcnow()))
        except Exception:
            log.warning("no price data for %s", s.symbol)
    db.commit()
```

`app/seed.py` (runs once as an `init` container)

```python
import pandas as pd
from .db import Base, engine, SessionLocal
from .models import Stock

def run():
    Base.metadata.create_all(engine)
    df = pd.read_csv("data/watchlist.csv")
    with SessionLocal() as db:
        for r in df.itertuples():
            db.merge(Stock(symbol=r.symbol, name=r.name,
                           yahoo_ticker=r.yahoo_ticker, news_query=r.news_query))
        db.commit()
    print(f"seeded {len(df)} stocks")

if __name__ == "__main__":
    run()
```

`app/worker.py`

```python
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from .config import settings
from .db import SessionLocal
from .news import ingest_all
from .prices import refresh_prices

logging.basicConfig(level=logging.INFO)

def run_news():
    with SessionLocal() as db:
        ingest_all(db)

def run_prices():
    with SessionLocal() as db:
        refresh_prices(db)

if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    sched = BlockingScheduler(timezone="Asia/Kolkata")
    sched.add_job(run_prices, "interval", minutes=settings.price_interval_min,
                  next_run_time=now, max_instances=1, coalesce=True)
    sched.add_job(run_news, "interval", minutes=settings.news_interval_min,
                  next_run_time=now, max_instances=1, coalesce=True)
    sched.start()
```

**Checkpoint:** run `python -m app.seed`, then `python -c "from app.db import SessionLocal; from app.news import ingest_all; ingest_all(SessionLocal())"`. Query the `news` table and confirm rows with sentiment labels exist **before** writing the API.

## 4. Step 3: API (1.5 hrs)

`app/schemas.py`

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    symbol: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    price_updated_at: datetime | None = None
    stale: bool = True

class NewsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    symbol: str
    title: str
    url: str
    source: str | None
    published_at: datetime
    sentiment: str
    confidence: float
    compound: float

class SummaryOut(BaseModel):
    symbol: str
    positive: int
    negative: int
    neutral: int
    avg_compound: float
    window_hours: int
```

`app/main.py`

```python
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session
from .db import get_db
from .models import Stock, News, Price
from .schemas import StockOut, NewsOut, SummaryOut

app = FastAPI(title="Indian Stock News Sentiment API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["GET"], allow_headers=["*"])

Sentiment = Literal["positive", "negative", "neutral"]

@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(func.now().select())
    return {"status": "ok"}

@app.get("/api/v1/stocks", response_model=list[StockOut])
def list_stocks(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    rows = db.query(Stock, Price).outerjoin(Price, Price.symbol == Stock.symbol).all()
    out = []
    for s, p in rows:
        out.append(StockOut(
            symbol=s.symbol, name=s.name,
            price=p.price if p else None,
            change_pct=p.change_pct if p else None,
            price_updated_at=p.updated_at if p else None,
            stale=(not p) or (now - p.updated_at > timedelta(minutes=30))))
    return out

@app.get("/api/v1/stocks/{symbol}/news", response_model=list[NewsOut])
def stock_news(symbol: str, sentiment: Sentiment | None = None,
               limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
               db: Session = Depends(get_db)):
    symbol = symbol.upper()
    if not db.get(Stock, symbol):
        raise HTTPException(404, "Unknown symbol")
    q = db.query(News).filter(News.symbol == symbol)
    if sentiment:
        q = q.filter(News.sentiment == sentiment)
    return q.order_by(News.published_at.desc()).offset(offset).limit(limit).all()

@app.get("/api/v1/stocks/{symbol}/sentiment-summary", response_model=SummaryOut)
def summary(symbol: str, hours: int = Query(48, ge=1, le=720),
            db: Session = Depends(get_db)):
    symbol = symbol.upper()
    if not db.get(Stock, symbol):
        raise HTTPException(404, "Unknown symbol")
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (db.query(News.sentiment, func.count(), func.avg(News.compound))
            .filter(News.symbol == symbol, News.published_at >= since)
            .group_by(News.sentiment).all())
    counts = {r[0]: r[1] for r in rows}
    total = sum(counts.values())
    avg = (sum(r[1] * float(r[2]) for r in rows) / total) if total else 0.0
    return SummaryOut(symbol=symbol, positive=counts.get("positive", 0),
                      negative=counts.get("negative", 0),
                      neutral=counts.get("neutral", 0),
                      avg_compound=round(avg, 3), window_hours=hours)

@app.get("/api/v1/news", response_model=list[NewsOut])
def all_news(sentiment: Sentiment | None = None,
             limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    q = db.query(News)
    if sentiment:
        q = q.filter(News.sentiment == sentiment)
    return q.order_by(News.published_at.desc()).limit(limit).all()
```

**Checkpoint:** `uvicorn app.main:app --reload`, open `http://localhost:8000/docs`, and call every endpoint. All must return 200 with data.

## 5. Step 4: Dashboard (2 hrs)

`dashboard/app.py`

```python
import os, requests, pandas as pd, plotly.express as px, streamlit as st
from streamlit_autorefresh import st_autorefresh

API = os.getenv("API_URL", "http://localhost:8000") + "/api/v1"
st.set_page_config(page_title="Indian Stock News Sentiment", layout="wide")
st_autorefresh(interval=60_000, key="refresh")

@st.cache_data(ttl=45)
def get(path, **params):
    r = requests.get(f"{API}{path}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()

COLORS = {"positive": "#16a34a", "negative": "#dc2626", "neutral": "#6b7280"}

try:
    stocks = get("/stocks")
except Exception:
    st.error("API unreachable. Retrying automatically.")
    st.stop()

st.title("Indian Stock News Sentiment")
names = {f"{s['symbol']}: {s['name']}": s for s in stocks}
choice = st.sidebar.selectbox("Stock", list(names))
filt = st.sidebar.radio("Sentiment", ["all", "positive", "negative", "neutral"])
s = names[choice]

c1, c2 = st.columns([1, 2])
with c1:
    if s["price"] is not None:
        st.metric(s["symbol"], f"₹{s['price']:,.2f}", f"{s['change_pct']}%")
        if s["stale"]:
            st.caption("Price may be delayed or stale")
    else:
        st.info("Price not available yet")
    sm = get(f"/stocks/{s['symbol']}/sentiment-summary")
    st.caption(f"Net sentiment (last {sm['window_hours']}h): {sm['avg_compound']:+.2f}")
    df = pd.DataFrame({"sentiment": ["positive", "negative", "neutral"],
                       "count": [sm["positive"], sm["negative"], sm["neutral"]]})
    if df["count"].sum():
        st.plotly_chart(px.pie(df, names="sentiment", values="count", hole=0.5,
                               color="sentiment", color_discrete_map=COLORS),
                        use_container_width=True)

with c2:
    params = {} if filt == "all" else {"sentiment": filt}
    news = get(f"/stocks/{s['symbol']}/news", limit=30, **params)
    if not news:
        st.info("No recent news for this filter.")
    for n in news:
        t = pd.to_datetime(n["published_at"]).tz_convert("Asia/Kolkata")
        st.markdown(
            f"<div style='border-left:6px solid {COLORS[n['sentiment']]};padding:6px 12px;margin:8px 0'>"
            f"<a href='{n['url']}' target='_blank'><b>{n['title']}</b></a><br>"
            f"<small>{n['source'] or ''} · {t:%d %b, %I:%M %p} IST · "
            f"<b style='color:{COLORS[n['sentiment']]}'>{n['sentiment'].upper()}</b> "
            f"({n['confidence']:.0%})</small></div>", unsafe_allow_html=True)

st.caption("Sentiment is model-generated from headlines and is not investment advice.")
```

## 6. Step 5: Docker packaging (1.5 hrs)

`Dockerfile` (the model is downloaded at **build** time, so there is no network dependency at demo time)

```dockerfile
FROM python:3.11-slim
WORKDIR /srv
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification as M; AutoTokenizer.from_pretrained('ProsusAI/finbert'); M.from_pretrained('ProsusAI/finbert')"
COPY . .
```

`.env`

```
DATABASE_URL=postgresql+psycopg2://app:app@db:5432/stocks
API_URL=http://api:8000
```

`docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16
    environment: {POSTGRES_USER: app, POSTGRES_PASSWORD: app, POSTGRES_DB: stocks}
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d stocks"]
      interval: 5s
      retries: 10
  init:
    build: .
    command: python -m app.seed
    env_file: .env
    depends_on: {db: {condition: service_healthy}}
  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    env_file: .env
    ports: ["8000:8000"]
    depends_on: {init: {condition: service_completed_successfully}}
    restart: unless-stopped
  worker:
    build: .
    command: python -m app.worker
    env_file: .env
    depends_on: {init: {condition: service_completed_successfully}}
    restart: unless-stopped
  dashboard:
    build: .
    command: streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0
    env_file: .env
    ports: ["8501:8501"]
    depends_on: [api]
    restart: unless-stopped
volumes:
  pgdata:
```

Run: `docker compose up --build`. Dashboard: `localhost:8501`. Swagger: `localhost:8000/docs`.

## 7. Step 6: Tests (45 min)

`tests/test_basic.py`

```python
from app.sentiment import score_batch

def test_sentiment_direction():
    r = score_batch(["Company reports record profit, shares surge",
                     "Company faces fraud probe, shares crash"])
    assert r[0]["label"] == "positive"
    assert r[1]["label"] == "negative"
    assert -1 <= r[0]["compound"] <= 1
```

Also add one `TestClient` test per endpoint (health returns 200, unknown symbol returns 404).

## 8. Failure-proofing (the "no loopholes" list)

| Risk | Mitigation |
| --- | --- |
| Yahoo rate-limits or breaks | Prices persist in DB; the API marks `stale: true`; failures never overwrite old data |
| Google News returns nothing or blocks | Per-stock try/except, 0.7s delay between requests, dashboard shows "No recent news" |
| Duplicate articles | Unique `(symbol, url_hash)` constraint plus pre-check |
| Model download fails on demo day | Baked into the Docker image at build time |
| Two workers double-ingest | `max_instances=1`, `coalesce=True`, one worker container |
| Tables missing when API starts | One-shot `init` container; others wait on `service_completed_successfully` |
| Timezone confusion | Store UTC, display IST |
| Wrong tickers | `verify_tickers.py` before seeding |
| Wi-Fi dies during demo | **Backup plan below** |
| Market closed during demo | Prices show last close; news still flows. Say so upfront |

**Backup plan (mandatory):** run the stack for 2+ hours before the demo so the DB is full. Then run `docker compose exec db pg_dump -U app stocks > backup.sql` and record a 2-minute screen video of the working dashboard. If anything fails live, you still have both.

## 9. Timeline to noon (adjust to your start time)

1. **Hour 0–1:** Step 1 (env, watchlist, ticker verification)
2. **Hour 1–3:** Step 2 (models, sentiment, news, prices, seed, worker), pass the checkpoint
3. **Hour 3–4.5:** Step 3 (API), pass the Swagger checkpoint
4. **Hour 4.5–6.5:** Step 4 (dashboard)
5. **Hour 6.5–8:** Step 5 (Docker), full `docker compose up --build` from a clean state
6. **Hour 8–9:** Step 6 (tests), README, architecture diagram
7. **Final 3 hours before noon:** feature freeze. Only bug fixes. Run the stack, take the backup, rehearse the demo twice

**Rule:** if a step runs 1 hr over, cut scope (fewer stocks, drop the pie chart), never cut the checkpoints.

## 10. Demo script (3 minutes)

1. Show the architecture in one sentence: *RSS + market data → worker → FinBERT → Postgres → FastAPI → dashboard.*
2. Open Swagger, call `/stocks/RELIANCE/news?sentiment=negative`.
3. Switch to the dashboard, pick a stock, filter positive vs negative, click one article.
4. Say the limits yourself: headline-level sentiment, a 20–50 stock watchlist, free-tier data that may be delayed, and the production upgrade path (broker API such as Zerodha or Upstox for true real-time ticks, Kafka for streaming, Redis cache).

## 11. README must contain

Problem, architecture diagram, stack and why, `docker compose up` instructions, endpoint list, limitations, and next steps. Reviewers read this first.

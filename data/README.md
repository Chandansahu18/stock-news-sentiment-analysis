# Data boundaries

The approved `watchlist.csv` contains 20 stock metadata rows.
Its columns are `symbol`, `name`, `yahoo_ticker`, and `news_query`.
The company names and symbols come from the official Nifty 50 constituent export.
The approved download and generation completed on 9 October 2026.
No mock company rows enter this file.

`watchlist.source.json` records the source URL, retrieval time, selection method, and hashes.
The raw source lives in ignored `runtime/nifty50-source.csv`.
Do not replace missing official constituents with mock rows.
The selection is the user-approved 20-stock subset, not a market-cap ranking.
The official source lists all 20 symbols in this snapshot.

Ticker validation must pass before database seeding.
Official constituent membership does not prove Yahoo ticker availability.
The `.NS` tickers remain unverified until the next approved live-data operation.
Record both scope and source limitations in the project README.

Live prices and news belong in PostgreSQL, not tracked CSV dumps.
Store model files in an ignored model directory.
Store database backups in `data/backups/`, which Git ignores.
Do not commit real credentials or database backups.

Every data preparation, download, initialization, or ingestion operation requires separate approval.

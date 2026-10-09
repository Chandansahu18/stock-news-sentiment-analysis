# Explicit project operations

Scripts will support ticker verification, approved model downloads, and approved maintenance operations.
Each script must explain its inputs, outputs, network access, and exit status.
Importing a script must not run its operation.

The first planned script is `verify_tickers.py`.
It will check every ticker from the approved CSV with bounded provider requests.
It must report failed tickers and return a failing exit status when checks fail.
It must not silently remove stocks from the watchlist.

The official watchlist commands live in `stock_sentiment.ingestion.watchlist`.
Use `python -m` entry points instead of manipulating import paths inside scripts.
The module exposes separate `download` and `generate` commands.
See `docs/setup.md` for approval rules and command examples.
The ticker verification script does not exist yet.
Request approval before executing each data operation.

# Explicit project operations

Scripts will support ticker verification, approved model downloads, and approved maintenance operations.
Each script must explain its inputs, outputs, network access, and exit status.
Importing a script must not run its operation.

The first planned script is `verify_tickers.py`.
It will check every ticker from the approved CSV with bounded provider requests.
It must report failed tickers and return a failing exit status when checks fail.
It must not silently remove stocks from the watchlist.

No operational scripts exist yet.
Request approval before executing each data operation.

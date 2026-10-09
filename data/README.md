# Data boundaries

The approved `watchlist.csv` will contain stock metadata only.
Its columns will be `symbol`, `name`, `yahoo_ticker`, and `news_query`.
The user approved CSV preparation, then requested real company metadata from the internet.
Watchlist preparation has not started because external download approval is pending.
Use an official source rather than invented or manually guessed company rows.
Record the source URL, retrieval time, and content hash for the generated watchlist.
Do not replace missing official constituents with mock rows.

Ticker validation must pass before database seeding.
Yahoo availability does not prove current Nifty 50 membership.
Record both scope and source limitations in the project README.

Live prices and news belong in PostgreSQL, not tracked CSV dumps.
Store model files in an ignored model directory.
Store database backups in `data/backups/`, which Git ignores.
Do not commit real credentials or database backups.

Every data preparation, download, initialization, or ingestion operation requires separate approval.

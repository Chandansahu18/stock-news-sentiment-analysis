# Data boundaries

The approved `watchlist.csv` will contain stock metadata only.
Its columns will be `symbol`, `name`, `yahoo_ticker`, and `news_query`.
Watchlist preparation requires explicit approval and has not started.

Ticker validation must pass before database seeding.
Yahoo availability does not prove current Nifty 50 membership.
Record both scope and source limitations in the project README.

Live prices and news belong in PostgreSQL, not tracked CSV dumps.
Store model files in an ignored model directory.
Store database backups in `data/backups/`, which Git ignores.
Do not commit real credentials or database backups.

Every data preparation, download, initialization, or ingestion operation requires separate approval.

# Dashboard module

The planned dashboard uses Streamlit and calls the FastAPI service.
It must not query PostgreSQL or run FinBERT directly.

The first release will provide stock selection, sentiment filtering, cached prices, and recent headlines.
It will show timestamps in IST and disclose delayed daily-close prices.
It must handle empty watchlists, empty news results, and API failures.
It must not render unescaped external headlines as trusted HTML.

Implementation starts after the API checkpoint.

# Module responsibilities and reasons

This document describes the target architecture.
Only the package foundation exists now.

| Module | Responsibility | Why the boundary exists |
| --- | --- | --- |
| `core` | Read and validate settings. Configure logging. | Keeps environment choices outside business logic. |
| `db` | Define models, sessions, and schema initialization. | Centralizes transactions and persistent record constraints. |
| `providers` | Fetch RSS and Yahoo price responses. | Isolates network timeouts, source changes, and source failures. |
| `services` | Score headlines and query summaries. | Keeps processing independent of HTTP routes and schedules. |
| `ingestion` | Validate the watchlist, seed stocks, and store refresh results. | Makes database writes explicit and repeatable. |
| `worker` | Schedule independent price and news jobs. | Keeps network requests and inference outside API requests. |
| `api` | Validate HTTP input and return defined response schemas. | Gives the dashboard a stable read contract. |
| `dashboard` | Select stocks, filter news, and show summaries. | Keeps presentation outside backend processing. |
| `scripts` | Run explicit verification and maintenance operations. | Makes checkpoints easy to repeat and review. |
| `tests` | Check behavior without unnecessary external access. | Catches failures before approved live operations. |

## Data flow

1. Read the approved CSV and verify each Yahoo ticker.
2. Initialize PostgreSQL and seed the verified stock metadata.
3. Fetch prices and recent RSS headlines with bounded requests.
4. Remove known article hashes before sentiment inference.
5. Score new headlines in batches with a local FinBERT model.
6. Store results in a transaction with duplicate protection.
7. Serve cached records through the API.
8. Show the results and source limitations in the dashboard.

Each preparation, download, initialization, and ingestion operation requires approval.

## Reliability rules

- Keep the last valid price when the provider fails.
- Separate the market observation time from the retrieval time.
- Identify daily-close prices explicitly.
- Use timezone-aware UTC timestamps in persistent records.
- Use IST only for presentation.
- Enforce uniqueness on each stock and article URL hash.
- Use request timeouts and bounded fetch sizes.
- Run one worker. Do not claim scheduler settings coordinate separate worker processes.
- Load FinBERT lazily inside the worker, not inside the API.
- Keep inference independent of network downloads during a demo.
- Show useful empty and error states in the dashboard.
- Treat headlines and URLs as untrusted input when rendering the dashboard.

## Structure adjustment from the guide

The guide places backend files in a flat `app/` directory.
The project uses an installable `src/stock_sentiment/` package.
Subpackages will separate configuration, persistence, external providers, processing, and HTTP routes.
This changes module paths, not the selected technology or demo scope.

## Production boundary

The demo architecture does not provide authentication, exchange-grade data, or high availability.
Database credentials must not use the guide's public `app:app` example.
Deployment versions must be pinned after installation and verification.
Production upgrades are outside the initial demo scope.

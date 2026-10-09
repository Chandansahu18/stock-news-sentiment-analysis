# Setup and checkpoints

## Current environment

- The sandbox provides Python 3.12.3 and Git 2.43.0.
- The guide selects Python 3.11 for the future Docker image.
- The package declares Python 3.11 and 3.12 support as a target.
- No project dependencies have been installed or tested yet.
- No Docker command has run for this project.
- The official-source watchlist exists and passed local validation.
- No model or database has been built. The user paused live ticker verification.
- No ticker-check dependencies were installed and no Yahoo price requests ran.

## Approval procedure

Before each Docker or data operation, record:

1. The exact command or file operation.
2. The purpose and expected output.
3. External hosts and downloads, if any.
4. Local files, containers, volumes, or database records that change.
5. The expected resource use and possible failures.

Run only the approved operation.
Record the result in `execution-log.md`.
Ask again before the next operation.

## Dependency setup: not executed

Use an isolated virtual environment for local Python dependencies.
Install the smallest dependency set needed for the current checkpoint.
The ticker checkpoint needs `yfinance`; it does not need FinBERT or Streamlit.
Install CPU-only PyTorch from `https://download.pytorch.org/whl/cpu` before worker inference.
Use PyTorch 2.6 or newer to satisfy the selected Transformers security requirements.
Do not download the FinBERT model as a side effect of importing modules.
Resolve and pin tested dependencies before the Docker build.

## Guide checkpoints

| Order | Checkpoint | Completion evidence |
| --- | --- | --- |
| 1 | Watchlist and live ticker verification | Each accepted ticker returns valid prices. Record failures without silently changing coverage. |
| 2 | Core backend and stored data | Approved stock metadata, prices, and scored headlines exist in PostgreSQL. |
| 3 | API | Health and data endpoints pass normal, empty, and invalid-input tests. |
| 4 | Dashboard | Stock selection, sentiment filters, empty states, and IST timestamps work. |
| 5 | Docker | Approved builds and startup produce the five expected services. |
| 6 | Verification and demo backup | Tests pass, the backup succeeds, and the dashboard recording exists. |

The guide places Docker after the dashboard.
The core database checkpoint still needs PostgreSQL earlier.
If Docker supplies that early database, request approval for that operation before it runs.

## Official watchlist operations

The approved source download completed with one public HTTPS request.
The importer validated all 50 constituent rows before generation.
The generation step preserved official names for all 20 approved symbols.

The following commands document the reusable operations.
**Do not rerun either operation without a new approval.**
Each command refuses to overwrite existing outputs.

Download operation:

```bash
PYTHONPATH=src python3 -m stock_sentiment.ingestion.watchlist download
```

Generation operation:

```bash
PYTHONPATH=src python3 -m stock_sentiment.ingestion.watchlist generate \
  --source-sha256 <sha256-from-download-output> \
  --retrieved-at <utc-timestamp-from-download-output>
```

The generation command never requests a network resource.
It checks the source hash before it writes the CSV and receipt.
It fails when an approved symbol is absent from the official source.
The source receipt records retrieval time, not the index's effective rebalance date.

Offline importer checks:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
```

All 13 checks passed. The tests use in-memory examples and a mocked network adapter.
The examples do not enter the project watchlist.
Separate local checks matched the generated rows against the actual downloaded source.
No live prices, news, or model inference ran during these checks.

## Paused live ticker checkpoint

The user selected `Hold live ticker checks` on 9 October 2026 at 13:42 UTC.
Do not install ticker-check dependencies or request Yahoo price data.
The official-source watchlist remains complete.
The guide requires live ticker verification before backend data building.
Keep that checkpoint paused until the user gives a new approval.

## Future Docker startup: unavailable

The target services are `db`, `init`, `api`, `worker`, and `dashboard`.
The `init` service will wait for PostgreSQL readiness.
The API and worker will wait for successful initialization.
The model will download during the approved image build, not during a demo request.
Docker files and executable startup instructions will follow the Docker approval checkpoint.

## Remote Git setup: pending

The repository has no active remote.
The user selected `https://github.com/Chandansahu18/stock-sentiment`.
The access check failed because the connected datasource does not provide this repository.
This check does not prove whether the repository exists.
Create the repository if needed and grant the connected GitHub integration access.
Push only after access succeeds and the remote destination is confirmed.
Local commits do not provide an off-machine backup.
Commit author and committer settings use the owner's identity.
The authenticated push account depends on the GitHub connection, not these settings.

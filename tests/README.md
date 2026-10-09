# Verification strategy

No application tests exist yet because only the package foundation exists.

## Offline unit tests

Test settings, CSV validation, response mapping, deduplication, summary calculations, and error handling.
Mock provider requests and sentiment inference.
Do not contact Yahoo, Google News, or Hugging Face during the offline test run.

## Integration tests

Use an isolated PostgreSQL test database.
Check initialization, uniqueness constraints, transactions, and API queries.
Database initialization requires approval even for a test database.

## Live and model tests

Mark external data tests as `live`.
Mark actual FinBERT tests as `model`.
Run these only after the relevant data operation receives approval.
Record the provider result and verification time.

## Dashboard checks

Verify stock selection, sentiment filtering, timestamps, stale labels, empty states, and source links.
Keep required screenshots and recordings outside the tracked source tree.

## Completion evidence

Report exact commands and results.
Do not claim an endpoint, model, or container works from a syntax check alone.

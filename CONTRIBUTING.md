# Development rules

## Keep the implementation understandable

Explain each module's responsibility in its docstring.
Put cross-module decisions in `docs/architecture.md`.
Update `README.md` and `docs/execution-log.md` with each completed checkpoint.
Mark planned behavior separately from verified behavior.

## Keep Git history useful

Use a branch whose name starts with `vorflux/`.
Make a focused commit for each completed module or coherent checkpoint.
Run the relevant checks before each feature commit.
Push each completed feature after the remote destination is confirmed.
Use feature branches and reviewed pull requests to protect the base branch.
Do not treat the final upload as a substitute for incremental feature history.
Use commit prefixes such as `chore:`, `feat:`, `fix:`, `test:`, and `docs:`.
Do not commit credentials, model weights, generated database files, or database backups.
Do not push until the user provides and authorizes a remote repository.
Use the project owner's approved name and email for commit author and committer fields.
Do not claim that commit settings change the authenticated GitHub account.
Confirm the user's authentication requirement before the first push.
The user requires `Chandansahu18` for authenticated pushes as well as commit attribution.
Do not push through an agent or app account even if that account has repository access.

## Keep runtime operations explicit

Imports must not download models, collect data, create tables, or start schedules.
Expose those actions through explicit commands or service entry points.
Request approval before every Docker or data operation.
Approval must cover the exact operation and its effects.
Do not interpret approval for one operation as approval for the next operation.
Document source failures. Do not present synthetic data as live data.

## Keep module boundaries clear

The dashboard calls the API.
API routes validate input and delegate to database queries or services.
Providers handle external requests and timeouts.
The worker controls refresh schedules and database transactions.
The sentiment service only scores supplied headlines.
Database models enforce record constraints.

## Verification

Use offline unit tests for pure functions and mocked providers.
Use an isolated test database for integration tests.
Mark external-source tests as `live` and FinBERT tests as `model`.
Keep live and model tests outside the default offline test run.
Report test failures and missing verification clearly.

# Publish from your personal GitHub account

## What this bundle contains

The bundle contains the complete local Git history and three local branches:

- `main`: the original repository initialization.
- `vorflux/project-foundation`: project structure, documentation, and approval controls.
- `vorflux/official-watchlist`: the official-source CSV, importer, offline tests, and current documentation.

**This is not the complete application.**
The API, database, worker, FinBERT integration, dashboard, and Docker setup are not implemented.
Live Yahoo ticker checks remain paused at your request.
No further data or Docker operation receives approval through these publishing instructions.

The bundle contains tracked Git objects, not the sandbox configuration or credentials.
It excludes the raw runtime download, environments, model files, and database backups.
The committed source receipt documents the approved download.

## 1. Download and restore the local history

Download `stock-news-sentiment-analysis.bundle`.
Run these commands on your own computer from the download directory:

```bash
git clone --branch vorflux/official-watchlist stock-news-sentiment-analysis.bundle stock-news-sentiment-analysis
cd stock-news-sentiment-analysis
git remote rename origin local-bundle
git remote add origin https://github.com/Chandansahu18/stock-news-sentiment-analysis.git
git config --local user.name "Chandan K Sahu"
git config --local user.email "chandanksahu24@gmail.com"
git config --local user.useConfigOnly true
```

The clone restores the feature commits without a network request.
The `local-bundle` remote retains the branch references from the bundle.
The new `origin` remote points to your GitHub repository.
The author settings preserve your identity on future commits.
These settings do not authenticate a push.

## 2. Confirm personal authentication

Authenticate your Git client as `Chandansahu18` on your own computer.
Do not use the Vorflux GitHub App credentials.
Do not paste a token into chat or a command.

If you use GitHub CLI, confirm its account:

```bash
gh api user --jq .login
```

The command must return `Chandansahu18`.
Stop if the command returns a different account or an authentication error.
This check verifies GitHub CLI, not an unrelated Git credential helper.
To use the verified GitHub CLI account for Git authentication, run:

```bash
gh auth setup-git
```

This command configures Git to use your GitHub CLI credentials.
It can change your computer's Git credential-helper settings for GitHub.
If you use another Git client, confirm that client's account before proceeding.

## 3. Publish the completed foundation

The destination repository was empty at the last access check.
If another person adds commits first, stop and inspect those commits.
Do not force-push or overwrite remote history.

Create the initial public `main` from the completed foundation:

```bash
git switch -c main local-bundle/vorflux/project-foundation
git push -u origin main
```

This step gives the repository a useful base branch instead of an empty root commit.
It preserves the foundation's original commit history.
It does not merge the watchlist feature into `main`.

## 4. Publish the completed watchlist feature

```bash
git switch vorflux/official-watchlist
git push -u origin vorflux/official-watchlist
```

This step publishes the completed watchlist feature separately.
The feature preserves official company names and records source hashes.
The derived Yahoo tickers remain unverified.

Repository:
https://github.com/Chandansahu18/stock-news-sentiment-analysis

Create the feature pull request from your own account:
https://github.com/Chandansahu18/stock-news-sentiment-analysis/compare/main...vorflux/official-watchlist?expand=1

Review the feature before merging it.
Do not describe this foundation and watchlist as a complete application.

## 5. Optional offline verification

The tests require Python 3.11 or 3.12 but no installed project dependencies.
They use in-memory examples and mocked requests.
They do not fetch live market data.

For Linux or macOS:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests/unit -v
```

For PowerShell:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = "src"
python -m unittest discover -s tests/unit -v
```

All 13 tests passed in the sandbox.
No Yahoo, news, model, database, or Docker operation ran during verification.

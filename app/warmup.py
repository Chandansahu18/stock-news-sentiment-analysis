"""Start-up work done in the background, so the first user does not wait for it.

* Loading the FinBERT model takes about 10 seconds.
* Reading the NSE stock list takes a moment (and about 3 seconds if it has to be downloaded).
Both run in their own threads while the server is already answering requests. A request that needs one
of them before it is ready simply waits for the load that is already running; nothing loads twice.
"""

from __future__ import annotations

import logging
import threading

from app.config import get_settings
from app.integrations import finbert
from app.services import stocks

log = logging.getLogger(__name__)


def _run_safely(description: str, task) -> None:
    try:
        task()
        log.info("Warm-up finished: %s", description)
    except Exception:  # a failed warm-up must never stop the server; the first request retries it
        log.exception("Warm-up failed: %s", description)


def start_background_warmup() -> list[threading.Thread]:
    settings = get_settings()
    if not settings.preload_on_startup:
        return []
    tasks = {
        "NSE stock list": stocks.get_listing,
        "FinBERT model": lambda: finbert.load_model(settings.finbert_model),
    }
    threads = [
        threading.Thread(target=_run_safely, args=(name, task), name=f"warmup-{name}", daemon=True)
        for name, task in tasks.items()
    ]
    for thread in threads:
        thread.start()
    return threads

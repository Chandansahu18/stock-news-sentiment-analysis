"""Shared HTTP access for every outbound call (Upstox, Google News, the NSE stock list).

* One pooled session: connections are kept alive, so repeat calls skip the TLS handshake.
* A cap on simultaneous outbound requests, so a burst of users cannot flood a provider.
* A short retry for connection errors and 502/503/504 only. Never for 403 or 429: retrying a
  rate-limit or firewall block just makes it last longer.
"""

from __future__ import annotations

import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

MAX_SIMULTANEOUS_REQUESTS = 6
DEFAULT_TIMEOUT_SECONDS = 15

_request_slots = threading.BoundedSemaphore(MAX_SIMULTANEOUS_REQUESTS)


def _build_session() -> requests.Session:
    retry = Retry(
        total=2,
        connect=2,
        read=0,  # a slow answer is not retried; the caller decides what to do
        backoff_factor=0.3,
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=MAX_SIMULTANEOUS_REQUESTS)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_session = _build_session()


def get(url: str, params: dict | None = None, headers: dict | None = None, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> requests.Response:
    with _request_slots:
        return _session.get(url, params=params, headers=headers, timeout=timeout)

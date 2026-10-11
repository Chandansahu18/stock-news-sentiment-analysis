"""One lock per cache key.

When several users ask for the same stock at the same moment, only the first one fetches and scores
the news; the others wait on this lock and then read the freshly cached result. This keeps upstream
API calls and model work to one per stock instead of one per user.
"""

from __future__ import annotations

import threading

_locks: dict[str, threading.Lock] = {}
_registry_guard = threading.Lock()


def lock_for(key: str) -> threading.Lock:
    with _registry_guard:
        return _locks.setdefault(key, threading.Lock())

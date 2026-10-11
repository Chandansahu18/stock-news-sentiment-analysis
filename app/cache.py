"""Tiny JSON-file cache with a time limit. This is the ONLY module that touches the disk cache.

Everything else uses `get_cache()` and the three methods below, so moving to a real database later
(for example PostgreSQL) means writing one new class with `save`, `get_fresh` and `get_even_if_expired`.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import get_settings

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


class JsonFileCache:
    """Each key is stored as `<directory>/<key>.json` together with the time it was saved."""

    def __init__(self, directory: Path):
        self.directory = directory

    def save(self, key: str, data: Any) -> None:
        """Write atomically, so a reader never sees a half-written file."""
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self._file_for(key)
        record = {"saved_at": time.time(), "data": data}
        fd, temp_name = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle, ensure_ascii=False)
            os.replace(temp_name, target)
        except BaseException:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
            raise

    def get_fresh(self, key: str, max_age_seconds: int) -> Any | None:
        """The cached data if it is younger than `max_age_seconds`, otherwise None."""
        record = self._read(key)
        if record and (time.time() - record["saved_at"]) <= max_age_seconds:
            return record["data"]
        return None

    def get_even_if_expired(self, key: str) -> Any | None:
        """The cached data whatever its age. Used as a fallback when an upstream API is down."""
        record = self._read(key)
        return record["data"] if record else None

    def _file_for(self, key: str) -> Path:
        # Keys become file names, so anything that could escape the directory is replaced.
        safe_name = _UNSAFE_FILENAME_CHARS.sub("_", key).lstrip(".") or "_"
        return self.directory / f"{safe_name}.json"

    def _read(self, key: str) -> dict | None:
        try:
            with open(self._file_for(key), encoding="utf-8") as handle:
                record = json.load(handle)
            if isinstance(record, dict) and "data" in record and "saved_at" in record:
                return record
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return None


def get_cache() -> JsonFileCache:
    """The cache configured by CACHE_DIR (read on every call, so tests can point it elsewhere)."""
    return JsonFileCache(get_settings().cache_dir)

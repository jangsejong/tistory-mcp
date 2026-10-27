"""Abuse guard for publish/update — minimum interval + daily cap. State persists in a file."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

# Sync tools run on worker threads, so two publish calls issued in parallel by a client would
# both pass the interval check without this lock (and POST always creates a new post).
# Cross-process use (two clients at once) is not serialized.
_LOCK = threading.Lock()


class RateLimitError(Exception):
    pass


class RateLimiter:
    def __init__(
        self,
        path: Path,
        *,
        min_interval_sec: int,
        daily_cap: int,
        clock: Callable[[], float] = time.time,
    ):
        self._path = path
        self._min_interval = max(0, int(min_interval_sec))
        self._daily_cap = max(0, int(daily_cap))
        self._clock = clock

    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, state: dict) -> None:
        # A crash mid-write would leave an empty file and silently reset the limits on the
        # next load, so write to a temp file and replace atomically.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        os.replace(tmp, self._path)

    def check_and_record(self, action: str) -> None:
        with _LOCK:
            self._check_and_record(action)

    def _check_and_record(self, action: str) -> None:
        now = self._clock()
        today = time.strftime("%Y-%m-%d", time.localtime(now))
        state = self._load()
        if state.get("day") != today:
            state = {"day": today, "count": 0, "last_ts": float(state.get("last_ts") or 0.0)}
        last_ts = float(state.get("last_ts") or 0.0)
        if self._min_interval and now - last_ts < self._min_interval:
            wait = self._min_interval - (now - last_ts)
            raise RateLimitError(
                f"{action} 간격 제한: {wait:.0f}초 후 다시 시도하세요 "
                f"(TISTORY_MCP_MIN_INTERVAL_SEC={self._min_interval})"
            )
        count = int(state.get("count") or 0)
        if self._daily_cap and count >= self._daily_cap:
            raise RateLimitError(
                f"{action} 일일 상한 {self._daily_cap}건 도달 (TISTORY_MCP_DAILY_CAP). "
                "내일 다시 시도하세요"
            )
        state.update({"count": count + 1, "last_ts": now, "last_action": action})
        self._save(state)

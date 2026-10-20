"""A small in-memory rate limiter: at most `limit` requests per key per window.

In memory is enough because the API runs as one process. Fixed windows: all
counts reset together when the window rolls over, which also keeps memory
bounded to the keys seen in one window.
"""

import threading
import time
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._window_start = clock()
        self._counts: dict[str, int] = {}
        # Sync endpoints run on a thread pool, so two requests can arrive at once.
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        with self._lock:
            now = self.clock()
            if now - self._window_start >= self.window_seconds:
                self._window_start = now
                self._counts.clear()
            count = self._counts.get(key, 0) + 1
            self._counts[key] = count
            return count <= self.limit

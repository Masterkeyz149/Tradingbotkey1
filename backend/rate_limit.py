"""
Minimal in-process rate limiter (sliding window). Good enough for a
single-instance Railway deployment. If you ever scale to multiple
instances, swap this for a Redis-backed limiter -- the interface below
stays the same either way.
"""
import time
from collections import deque
from threading import Lock


class RateLimiter:
    def __init__(self, max_calls: int, per_seconds: int = 60):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self._calls: deque[float] = deque()
        self._lock = Lock()

    def allow(self) -> bool:
        now = time.time()
        with self._lock:
            while self._calls and now - self._calls[0] > self.per_seconds:
                self._calls.popleft()
            if len(self._calls) >= self.max_calls:
                return False
            self._calls.append(now)
            return True

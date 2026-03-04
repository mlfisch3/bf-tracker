from __future__ import annotations

import random
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_requests_per_minute: int, min_delay: float, max_delay: float) -> None:
        self.max_requests_per_minute = max_requests_per_minute
        self.min_delay = min_delay
        self.max_delay = max(max_delay, min_delay)
        self._timestamps: deque[float] = deque()
        self._last_call_at: float | None = None
        self._target_interval = (60.0 / self.max_requests_per_minute) if self.max_requests_per_minute > 0 else 0.0

    def _sleep_for_rate(self) -> None:
        if self.max_requests_per_minute <= 0:
            return
        now = time.time()
        window = 60.0
        while self._timestamps and now - self._timestamps[0] > window:
            self._timestamps.popleft()
        if len(self._timestamps) >= self.max_requests_per_minute:
            earliest = self._timestamps[0]
            wait_time = max(0.0, window - (now - earliest))
            time.sleep(wait_time)

    def wait(self) -> None:
        self._sleep_for_rate()
        now = time.time()
        jitter_wait = random.uniform(self.min_delay, self.max_delay) if self.max_delay > 0 else 0.0
        cadence_wait = 0.0
        if self._target_interval > 0 and self._last_call_at is not None:
            cadence_wait = max(0.0, self._target_interval - (now - self._last_call_at))
        wait_for = max(jitter_wait, cadence_wait)
        if wait_for > 0:
            time.sleep(wait_for)
        self._last_call_at = time.time()
        self._timestamps.append(self._last_call_at)

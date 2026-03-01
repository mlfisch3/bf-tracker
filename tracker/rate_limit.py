from __future__ import annotations

import random
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_requests_per_minute: int, min_delay: float, max_delay: float) -> None:
        self.max_requests_per_minute = max_requests_per_minute
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._timestamps: deque[float] = deque()

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
        jitter = random.uniform(self.min_delay, self.max_delay)
        time.sleep(jitter)
        self._timestamps.append(time.time())

from __future__ import annotations

import random
import time
from typing import Optional

import requests

from .rate_limit import RateLimiter


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


class FetchError(Exception):
    pass


def build_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
    }


def fetch_page(session: requests.Session, url: str, limiter: RateLimiter, max_retries: int) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        limiter.wait()
        try:
            response = session.get(url, headers=build_headers(), timeout=20)
            if response.status_code in {429, 403}:
                time.sleep(10 + attempt * 5)
            response.raise_for_status()
            return response.text
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2 + attempt * 2)
    raise FetchError(f"Failed to fetch {url}: {last_error}")

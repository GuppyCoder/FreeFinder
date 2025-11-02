"""HTTP client utilities with polite defaults."""

from __future__ import annotations

import random
import time
from typing import Optional, Tuple

import requests

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
DEFAULT_TIMEOUT = 15
DEFAULT_SLEEP_RANGE = (5.0, 8.0)


def _sleep_with_jitter(sleep_range: Optional[Tuple[float, float]]) -> None:
    """Pause for a random amount of time so our crawler looks less like a bot."""
    if not sleep_range:
        return
    low, high = sleep_range
    if low < 0 or high < low:
        raise ValueError("Invalid sleep range for jitter delay.")
    delay = random.uniform(low, high)
    time.sleep(delay)


def get_html(
    url: str,
    *,
    session: Optional[requests.Session] = None,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
    sleep_range: Optional[Tuple[float, float]] = DEFAULT_SLEEP_RANGE,
) -> str:
    """Fetch a URL and return response text, raising for bad status codes."""
    _sleep_with_jitter(sleep_range)
    client = session or requests
    # Matching real browser headers keeps Craigslist from blocking us immediately.
    headers = {
        "User-Agent": user_agent,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
    }
    response = client.get(url, timeout=timeout, headers=headers)
    response.raise_for_status()
    return response.text

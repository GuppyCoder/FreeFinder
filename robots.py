"""Robots.txt helper to ensure we only fetch allowed paths."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests

from fetcher import DEFAULT_TIMEOUT, DEFAULT_USER_AGENT


@lru_cache(maxsize=32)
def _load_parser(robots_url: str) -> RobotFileParser:
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        # Fetch robots.txt ourselves so we can cache the rules and reuse them.
        response = requests.get(
            robots_url,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
        if response.ok:
            parser.parse(response.text.splitlines())
            return parser
    except requests.RequestException:
        pass

    # Fall back to permissive default if robots.txt cannot be fetched.
    parser.parse([])
    return parser


def can_fetch(url: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
    """Return True if robots.txt allows fetching the provided URL."""
    parts = urlsplit(url)
    robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    # RobotFileParser needs the robots URL, not the page URL we want to fetch.
    parser = _load_parser(robots_url)
    return parser.can_fetch(user_agent, url)

"""Craigslist site adapter for FreeFinder."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from fetcher import get_html
from models import Item

SEARCH_PATH = "/search/zip"
SOURCE_NAME = "craigslist"
ID_PATTERN = re.compile(r"/(\d+)\.html")
DETAIL_TIME_FORMATS = ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%z")
DEFAULT_MAX_ITEMS = 120
DEFAULT_DETAIL_SLEEP_RANGE: Tuple[float, float] = (0.75, 1.5)
DEFAULT_MAX_AGE = timedelta(days=7)


def build_search_url(region: str, params: dict | None = None) -> str:
    base = f"https://{region}.craigslist.org{SEARCH_PATH}"
    if not params:
        return base
    return f"{base}?{urlencode(params)}"


def _extract_id(url: str, region: str) -> Optional[str]:
    match = ID_PATTERN.search(url)
    if not match:
        return None
    return f"{SOURCE_NAME}:{region}:{match.group(1)}"


def _parse_detail_timestamps(html: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    soup = BeautifulSoup(html, "lxml")
    posted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Craigslist stores both "posted" and "updated" timestamps in <time> tags.
    # We read both so we can treat a recently-edited listing as fresh.
    def _parse_value(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        for fmt in DETAIL_TIME_FORMATS:
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return None

    for info in soup.select("p.postinginfo"):
        time_tag = info.find("time")
        if not time_tag:
            continue
        value = _parse_value(time_tag.get("datetime") or time_tag.get_text(strip=True))
        if not value:
            continue
        text = info.get_text(" ", strip=True).lower()
        if "updated" in text:
            updated_at = value
        elif "posted" in text and posted_at is None:
            posted_at = value

    if not posted_at:
        fallback = soup.select_one("time.date[datetime]")
        posted_at = _parse_value(fallback.get("datetime") if fallback else None)

    return posted_at, updated_at


def _fetch_listing_times(
    url: str,
    session: Optional[requests.Session],
    sleep_range: Optional[Sequence[float]],
) -> Tuple[Optional[datetime], Optional[datetime]]:
    # Each listing only reveals its timestamps on the detail page, so we fetch it here.
    try:
        detail_html = get_html(
            url,
            session=session,
            sleep_range=tuple(sleep_range) if sleep_range else None,
        )
    except Exception:
        return None, None
    return _parse_detail_timestamps(detail_html)


def parse_listings(
    html: str,
    region: str,
    *,
    session: Optional[requests.Session] = None,
    max_items: Optional[int] = DEFAULT_MAX_ITEMS,
    detail_sleep_range: Tuple[float, float] = DEFAULT_DETAIL_SLEEP_RANGE,
    max_age: timedelta = DEFAULT_MAX_AGE,
    stop_at_stale: bool = True,
) -> Tuple[List[Item], Optional[Dict[str, str]]]:
    """Extract item listings from Craigslist search HTML."""
    soup = BeautifulSoup(html, "lxml")
    items: List[Item] = []
    stale_trigger: Optional[Dict[str, str]] = None
    stale_cutoff = datetime.now(timezone.utc) - max_age

    for result in soup.select("ol.cl-static-search-results li.cl-static-search-result"):
        link = result.find("a")
        if not link or not link.get("href"):
            continue

        href = link.get("href")
        url = urljoin(f"https://{region}.craigslist.org", href)

        item_id = _extract_id(url, region)
        if not item_id:
            continue

        title_tag = link.select_one("div.title")
        title = title_tag.get_text(strip=True) if title_tag else link.get_text(strip=True)

        location_tag = link.select_one("div.location")
        location = location_tag.get_text(strip=True) if location_tag else None

        price_tag = link.select_one("div.price")
        price = None
        if price_tag:
            digits = re.sub(r"[^\d.]", "", price_tag.get_text())
            price = float(digits) if digits else None

        posted_at, updated_at = _fetch_listing_times(url, session, detail_sleep_range)
        reference_time = None
        if posted_at:
            posted_at = posted_at.astimezone(timezone.utc)
            reference_time = posted_at
        if updated_at:
            updated_at = updated_at.astimezone(timezone.utc)
            if not reference_time or updated_at > reference_time:
                reference_time = updated_at

        # reference_time represents the latest activity (post or update) for this listing.
        if reference_time:
            if reference_time < stale_cutoff:
                if stale_trigger is None:
                    stale_trigger = {
                        "title": title,
                        "url": url,
                        "reference": reference_time.isoformat(),
                    }
                if stop_at_stale:
                    break
                continue
        else:
            continue

        item = Item(
            id=item_id,
            title=title,
            url=url,
            source=SOURCE_NAME,
            description=None,
            location=location,
            posted_at=reference_time,
            price=price,
        )
        items.append(item)
        if max_items and len(items) >= max_items:
            break

    return items, stale_trigger

"""Keyword-based filtering for FreeFinder listings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence, Tuple

from models import Item

# Keywords that indicate a listing is likely helpful for families in need.
INCLUDE_KEYWORDS: Tuple[str, ...] = (
    # Electronics & consoles
    "electronics",
    "xbox series x",
    "series x",
    "xbox",
    "nintendo switch",
    "switch",
    "console",
    "playstation",
    "ps5",
    "tablet",
    "laptop",
    "computer",
    "tv",
    "television",
    "monitor",
    "printer",
    # Household essentials
    "mattress",
    "bed",
    "bunk bed",
    "crib",
    "bassinet",
    "sofa",
    "couch",
    "futon",
    "table",
    "chair",
    "dresser",
    "shelves",
    "twin bed",
    "queen bed",
    # Gardening & outdoor support
    "garden",
    "gardening",
    "planter",
    "raised bed",
    "mulch",
    "compost bin",
    "plant",
    "plants",
    "seed",
    "seeds",
    "soil",
    "greenhouse",
    "irrigation",
    "hose",
    "shovel",
    "rake",
    "wheelbarrow",
)

# Keywords that should be excluded even if they match the include list.
EXCLUDE_KEYWORDS: Tuple[str, ...] = (
    "moving boxes",
    "moving box",
    "free boxes",
    "cardboard boxes",
    "dirt",
    "fill dirt",
    "manure",
)

MAX_ITEM_AGE = timedelta(days=7)


@dataclass(frozen=True)
class FilterOutcome:
    """Represents the filtering decision for a single item."""

    item: Item
    matched_keywords: Tuple[str, ...]
    excluded_keywords: Tuple[str, ...]


def _normalize(text: str) -> str:
    return text.lower()


def _find_matches(text: str, keywords: Sequence[str]) -> Tuple[str, ...]:
    normalized = _normalize(text)
    return tuple(keyword for keyword in keywords if keyword in normalized)


def is_recent(item: Item, now: datetime) -> bool:
    """Return True when the listing is newer than our age limit."""
    posted_at = item.posted_at
    if not posted_at:
        return False
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    else:
        posted_at = posted_at.astimezone(timezone.utc)
    return posted_at >= now - MAX_ITEM_AGE


def evaluate_item(item: Item) -> FilterOutcome:
    """Return matched/excluded keywords for an item."""
    text = f"{item.title} {item.description or ''}"
    matches = _find_matches(text, INCLUDE_KEYWORDS)
    exclusions = _find_matches(text, EXCLUDE_KEYWORDS)
    return FilterOutcome(item=item, matched_keywords=matches, excluded_keywords=exclusions)


def filter_items(items: Iterable[Item]) -> Tuple[List[Item], List[FilterOutcome]]:
    """
    Filter items by keyword lists.

    Returns a tuple of (kept_items, dropped_outcomes).
    """
    kept: List[Item] = []
    dropped: List[FilterOutcome] = []
    now = datetime.now(timezone.utc)

    for item in items:
        # Evaluate keyword matches once so we can reuse the result when explaining drops.
        # (This keeps the loop easy to read and avoids repeating logic.)
        outcome = evaluate_item(item)
        if not is_recent(item, now):
            dropped.append(outcome)
            continue
        if outcome.excluded_keywords or not outcome.matched_keywords:
            dropped.append(outcome)
            continue
        kept.append(item)

    return kept, dropped


def describe_rejection(outcome: FilterOutcome, *, now: Optional[datetime] = None) -> str:
    """Return a human-readable reason for excluding an item."""
    reference_time = now or datetime.now(timezone.utc)
    if not is_recent(outcome.item, reference_time):
        if not outcome.item.posted_at:
            return "missing posted date"
        posted_at = outcome.item.posted_at
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        else:
            posted_at = posted_at.astimezone(timezone.utc)
        return f"posted {posted_at.isoformat()} (older than 7 days)"
    if outcome.excluded_keywords:
        keywords = ", ".join(outcome.excluded_keywords)
        return f"excluded keywords: {keywords}"
    if not outcome.matched_keywords:
        return "no matching keywords"
    return "kept"

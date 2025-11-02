"""Core data models used across FreeFinder."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Item:
    """Represents a single free item listing."""

    id: str
    title: str
    url: str
    source: str
    description: Optional[str] = None
    location: Optional[str] = None
    posted_at: Optional[datetime] = None
    price: Optional[float] = None

    def as_row(self) -> tuple:
        """Return a SQLite-friendly tuple representation."""
        posted_at_iso = self.posted_at.isoformat() if self.posted_at else None
        # SQLite only stores plain strings, so we convert datetime objects beforehand.
        return (
            self.id,
            self.title,
            self.url,
            self.source,
            self.description,
            self.location,
            posted_at_iso,
            self.price,
        )

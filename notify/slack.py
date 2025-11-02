"""Slack notification helper (stubbed until webhook is available)."""

from __future__ import annotations

from typing import Optional

import requests


def send_message(webhook_url: Optional[str], text: str) -> None:
    """Send a message to Slack if a webhook URL is provided."""
    if not webhook_url:
        # No webhook means notifications are disabled, so quietly skip the request.
        return
    response = requests.post(webhook_url, json={"text": text}, timeout=10)
    response.raise_for_status()

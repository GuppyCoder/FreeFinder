"""Send push notifications via ntfy.sh."""

from __future__ import annotations

from typing import Optional

import requests


def send_message(
    topic: Optional[str],
    text: str,
    *,
    server: str = "https://ntfy.sh",
    username: Optional[str] = None,
    password: Optional[str] = None,
    token: Optional[str] = None,
    title: Optional[str] = None,
    priority: Optional[int] = None,
    click: Optional[str] = None,
) -> None:
    """Send a notification to an ntfy topic if provided."""
    if not topic:
        return

    url = f"{server.rstrip('/')}/{topic}"
    headers = {}
    auth = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif username and password:
        auth = (username, password)
    if title:
        headers["Title"] = title
    if priority:
        headers["Priority"] = str(priority)
    if click:
        headers["Click"] = click

    response = requests.post(url, data=text.encode("utf-8"), headers=headers, auth=auth, timeout=10)
    response.raise_for_status()

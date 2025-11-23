"""SMS notification helper using Twilio."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from twilio.rest import Client


@dataclass
class SmsConfig:
    """Configuration required to send an SMS message."""

    account_sid: str
    auth_token: str
    from_number: str
    to_number: str


def send_sms(config: Optional[SmsConfig], text: str) -> None:
    """Send an SMS message if configuration is provided."""
    if not config:
        # No SMS configuration means notifications are disabled.
        return
    client = Client(config.account_sid, config.auth_token)
    client.messages.create(body=text, from_=config.from_number, to=config.to_number)

"""Simple email notification helper over SMTP."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Iterable, Optional


@dataclass
class EmailConfig:
    """SMTP configuration for sending summary emails."""

    smtp_server: str
    smtp_port: int
    username: str
    password: str
    from_addr: str
    to_addr: str
    use_ssl: bool = False


def send_email(config: Optional[EmailConfig], subject: str, body_lines: Iterable[str]) -> None:
    """Send an email with the provided lines as the plain-text body."""
    if not config:
        return

    message = EmailMessage()
    message["From"] = config.from_addr
    message["To"] = config.to_addr
    message["Subject"] = subject
    message.set_content("\n".join(body_lines))

    if config.use_ssl:
        with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port) as smtp:
            smtp.login(config.username, config.password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(config.smtp_server, config.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(config.username, config.password)
            smtp.send_message(message)

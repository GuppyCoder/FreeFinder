"""Simple CLI entry point to crawl Craigslist free listings."""

from __future__ import annotations

import argparse
import os
from typing import Optional, Tuple

import requests

from fetcher import get_html
from filters import MAX_ITEM_AGE, describe_rejection, filter_items
from notify.ntfy import send_message as send_ntfy_message
from notify.email import EmailConfig, send_email
from notify.slack import send_message as send_slack_message
from notify.sms import SmsConfig, send_sms
from robots import can_fetch
from sites.craigslist import (
    DEFAULT_DETAIL_SLEEP_RANGE,
    DEFAULT_MAX_ITEMS,
    build_search_url,
    parse_listings,
)
from storage.sqlite import init_db, purge_stale_items, upsert_items

DEFAULT_REGION = "sanantonio"
DEFAULT_DB_PATH = "freefinder.db"
DEFAULT_DETAIL_SLEEP = DEFAULT_DETAIL_SLEEP_RANGE
DEFAULT_SORT = "date"


def crawl_once(
    region: str,
    db_path: str,
    webhook: Optional[str],
    sms_config: Optional[SmsConfig],
    email_config: Optional[EmailConfig],
    ntfy_config: dict,
    dry_run: bool,
    *,
    max_items: Optional[int],
    detail_sleep_range: Tuple[float, float],
    sort: Optional[str],
    postal: Optional[str],
    search_distance: Optional[int],
    stop_at_stale: bool,
) -> None:
    # Build the search query parameters exactly the way Craigslist expects them.
    params = {}
    if sort:
        params["sort"] = sort
    if postal:
        params["postal"] = postal
    if search_distance is not None:
        params["search_distance"] = str(search_distance)

    url = build_search_url(region, params=params or None)
    if not can_fetch(url):
        raise RuntimeError(f"robots.txt disallows fetching {url}")

    # Reuse one HTTP session so cookies/user-agent are shared across requests.
    with requests.Session() as session:
        html = get_html(url, session=session, sleep_range=None)
        items, stale_trigger = parse_listings(
            html,
            region,
            session=session,
            max_items=max_items or DEFAULT_MAX_ITEMS,
            detail_sleep_range=detail_sleep_range,
            max_age=MAX_ITEM_AGE,
            stop_at_stale=stop_at_stale,
        )
    if stale_trigger:
        print(
            "[INFO] Encountered listing older than a week; stopping crawl at "
            f"{stale_trigger['title']} ({stale_trigger['url']}) "
            f"last activity {stale_trigger['reference']}."
        )

    kept_items, dropped = filter_items(items)
    print(f"Parsed {len(items)} listings; keeping {len(kept_items)}, dropping {len(dropped)}.")

    if dry_run:
        # Dry-run prints everything to help you verify behaviour without touching the DB.
        for item in kept_items:
            print(f"[DRY RUN] {item.title} -> {item.url}")
        if dropped:
            print(f"[DRY RUN] Dropped {len(dropped)} items (see reasons below).")
            for outcome in dropped:
                reason = describe_rejection(outcome)
                print(f"[DROP] {reason} -> {outcome.item.title} ({outcome.item.url})")
        return

    connection = init_db(db_path)
    purged = purge_stale_items(connection)
    if purged:
        print(f"Removed {purged} items older than a week.")
    inserted = upsert_items(connection, kept_items)
    print(f"Processed {len(kept_items)} filtered items; upserted {inserted}.")

    if inserted and (webhook or sms_config or ntfy_config["topic"] or email_config):
        message = f"FreeFinder: {inserted} new free items in {region}."
        if webhook:
            send_slack_message(webhook, message)
        send_sms(sms_config, message)
        if email_config:
            lines = [message, ""]
            lines.append("New listings:")
            for item in kept_items:
                lines.append(f"- {item.title} -> {item.url}")
            send_email(email_config, subject="FreeFinder updates", body_lines=lines)
        send_ntfy_message(
            ntfy_config["topic"],
            message,
            server=ntfy_config["server"],
            username=ntfy_config["username"],
            password=ntfy_config["password"],
            token=ntfy_config["token"],
            title=ntfy_config["title"],
            priority=ntfy_config["priority"],
            click=ntfy_config["click"],
        )


def build_parser() -> argparse.ArgumentParser:
    """Describe the command-line options available to the user."""
    parser = argparse.ArgumentParser(description="Run a single Craigslist crawl.")
    parser.add_argument("--region", default=DEFAULT_REGION, help="Craigslist region subdomain")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="SQLite database path")
    parser.add_argument("--webhook", default=None, help="Slack webhook URL (optional)")
    parser.add_argument(
        "--sms-to",
        default=None,
        help="Phone number to notify via SMS (defaults to SMS_TO_NUMBER env var if unset)",
    )
    parser.add_argument(
        "--sms-from",
        default=None,
        help="Twilio phone number used to send SMS (defaults to TWILIO_FROM_NUMBER env var if unset)",
    )
    parser.add_argument(
        "--twilio-account",
        default=None,
        help="Twilio Account SID (defaults to TWILIO_ACCOUNT_SID env var if unset)",
    )
    parser.add_argument(
        "--twilio-token",
        default=None,
        help="Twilio Auth Token (defaults to TWILIO_AUTH_TOKEN env var if unset)",
    )
    parser.add_argument("--email-to", default=None, help="Email address to notify with item links")
    parser.add_argument("--email-from", default=None, help="From address for notification emails")
    parser.add_argument("--smtp-server", default=None, help="SMTP server hostname")
    parser.add_argument("--smtp-port", type=int, default=None, help="SMTP server port")
    parser.add_argument("--smtp-username", default=None, help="SMTP username")
    parser.add_argument("--smtp-password", default=None, help="SMTP password")
    parser.add_argument(
        "--smtp-use-ssl",
        action="store_true",
        help="Use SMTP SSL instead of STARTTLS",
    )
    parser.add_argument(
        "--ntfy-topic",
        default=None,
        help="ntfy.sh topic to post notifications to (defaults to NTFY_TOPIC env var if unset)",
    )
    parser.add_argument(
        "--ntfy-server",
        default=None,
        help="ntfy.sh server (defaults to NTFY_SERVER env var or https://ntfy.sh)",
    )
    parser.add_argument(
        "--ntfy-user",
        default=None,
        help="ntfy username for basic auth (defaults to NTFY_USER env var if unset)",
    )
    parser.add_argument(
        "--ntfy-password",
        default=None,
        help="ntfy password for basic auth (defaults to NTFY_PASSWORD env var if unset)",
    )
    parser.add_argument(
        "--ntfy-token",
        default=None,
        help="ntfy bearer token (defaults to NTFY_TOKEN env var if unset)",
    )
    parser.add_argument(
        "--ntfy-title",
        default=None,
        help="Custom ntfy notification title (defaults to NTFY_TITLE env var if unset)",
    )
    parser.add_argument(
        "--ntfy-priority",
        type=int,
        choices=range(1, 6),
        default=None,
        help="ntfy priority 1-5 (defaults to NTFY_PRIORITY env var if unset)",
    )
    parser.add_argument(
        "--ntfy-click",
        default=None,
        help="URL to open when tapping the ntfy notification (defaults to NTFY_CLICK env var if unset)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print items without storing")
    parser.add_argument(
        "--max-items",
        type=int,
        default=DEFAULT_MAX_ITEMS,
        help=f"Maximum number of listings to process per crawl (default: {DEFAULT_MAX_ITEMS})",
    )
    parser.add_argument(
        "--detail-sleep",
        type=float,
        nargs=2,
        metavar=("MIN", "MAX"),
        default=DEFAULT_DETAIL_SLEEP,
        help=(
            "Range of seconds to sleep between detail page requests "
            f"(default: {DEFAULT_DETAIL_SLEEP_RANGE[0]} {DEFAULT_DETAIL_SLEEP_RANGE[1]})"
        ),
    )
    parser.add_argument("--sort", default=DEFAULT_SORT, help="Craigslist sort parameter (e.g., date, rel)")
    parser.add_argument("--postal", default=None, help="Craigslist postal code filter")
    parser.add_argument(
        "--search-distance",
        type=int,
        default=None,
        help="Craigslist search distance (miles) when postal is provided",
    )
    parser.add_argument(
        "--allow-out-of-order",
        action="store_true",
        help="Do not stop when encountering listings older than the age threshold.",
    )
    return parser


def main() -> None:
    """Parse CLI arguments and kick off a single crawl."""
    args = build_parser().parse_args()
    detail_sleep_range = tuple(args.detail_sleep)
    if detail_sleep_range[0] < 0 or detail_sleep_range[1] < detail_sleep_range[0]:
        raise ValueError("Invalid --detail-sleep range. Ensure 0 <= MIN <= MAX.")
    max_items = args.max_items if args.max_items and args.max_items > 0 else DEFAULT_MAX_ITEMS
    if args.search_distance is not None and not args.postal:
        raise ValueError("--search-distance requires --postal to be set.")

    sms_to = args.sms_to or os.environ.get("SMS_TO_NUMBER")
    sms_from = args.sms_from or os.environ.get("TWILIO_FROM_NUMBER")
    twilio_account = args.twilio_account or os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = args.twilio_token or os.environ.get("TWILIO_AUTH_TOKEN")
    sms_config = None
    if sms_to:
        missing = [
            flag for flag, value in [
                ("--twilio-account/TWILIO_ACCOUNT_SID", twilio_account),
                ("--twilio-token/TWILIO_AUTH_TOKEN", twilio_token),
                ("--sms-from/TWILIO_FROM_NUMBER", sms_from),
            ] if not value
        ]
        if missing:
            missing_flags = ", ".join(missing)
            raise ValueError(
                f"SMS notifications requested but missing required Twilio settings: {missing_flags}."
            )
        sms_config = SmsConfig(
            account_sid=twilio_account,
            auth_token=twilio_token,
            from_number=sms_from,
            to_number=sms_to,
        )

    email_to = args.email_to or os.environ.get("EMAIL_TO")
    email_from = args.email_from or os.environ.get("EMAIL_FROM")
    smtp_server = args.smtp_server or os.environ.get("SMTP_SERVER")
    smtp_port_raw = args.smtp_port or os.environ.get("SMTP_PORT")
    smtp_username = args.smtp_username or os.environ.get("SMTP_USERNAME")
    smtp_password = args.smtp_password or os.environ.get("SMTP_PASSWORD")
    smtp_use_ssl = args.smtp_use_ssl or os.environ.get("SMTP_USE_SSL") == "1"
    email_config = None
    if email_to:
        missing_email = [
            flag for flag, value in [
                ("--smtp-server/SMTP_SERVER", smtp_server),
                ("--smtp-port/SMTP_PORT", smtp_port_raw),
                ("--smtp-username/SMTP_USERNAME", smtp_username),
                ("--smtp-password/SMTP_PASSWORD", smtp_password),
                ("--email-from/EMAIL_FROM", email_from),
            ] if not value
        ]
        if missing_email:
            missing_flags = ", ".join(missing_email)
            raise ValueError(f"Email notifications requested but missing settings: {missing_flags}.")
        smtp_port = int(smtp_port_raw)
        email_config = EmailConfig(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            username=smtp_username,
            password=smtp_password,
            from_addr=email_from,
            to_addr=email_to,
            use_ssl=smtp_use_ssl,
        )

    ntfy_topic = args.ntfy_topic or os.environ.get("NTFY_TOPIC")
    ntfy_config = {
        "topic": ntfy_topic,
        "server": args.ntfy_server or os.environ.get("NTFY_SERVER") or "https://ntfy.sh",
        "username": args.ntfy_user or os.environ.get("NTFY_USER"),
        "password": args.ntfy_password or os.environ.get("NTFY_PASSWORD"),
        "token": args.ntfy_token or os.environ.get("NTFY_TOKEN"),
        "title": args.ntfy_title or os.environ.get("NTFY_TITLE"),
        "priority": args.ntfy_priority or os.environ.get("NTFY_PRIORITY"),
        "click": args.ntfy_click or os.environ.get("NTFY_CLICK"),
    }
    if ntfy_config["username"] and ntfy_config["token"]:
        raise ValueError("Provide either ntfy user/pass or ntfy token, not both.")
    if ntfy_config["priority"] is not None:
        try:
            ntfy_config["priority"] = int(ntfy_config["priority"])
        except ValueError as exc:
            raise ValueError("ntfy priority must be an integer between 1 and 5.") from exc
        if ntfy_config["priority"] < 1 or ntfy_config["priority"] > 5:
            raise ValueError("ntfy priority must be between 1 and 5.")

    crawl_once(
        args.region,
        args.db_path,
        args.webhook,
        sms_config,
        email_config,
        ntfy_config,
        args.dry_run,
        max_items=max_items,
        detail_sleep_range=detail_sleep_range,
        sort=args.sort,
        postal=args.postal,
        search_distance=args.search_distance,
        stop_at_stale=not args.allow_out_of_order,
    )


if __name__ == "__main__":
    main()

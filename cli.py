"""Simple CLI entry point to crawl Craigslist free listings."""

from __future__ import annotations

import argparse
from typing import Optional, Tuple

import requests

from fetcher import get_html
from filters import MAX_ITEM_AGE, describe_rejection, filter_items
from notify.slack import send_message
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

    if inserted and webhook:
        message = f"FreeFinder: {inserted} new free items in {region}."
        send_message(webhook, message)


def build_parser() -> argparse.ArgumentParser:
    """Describe the command-line options available to the user."""
    parser = argparse.ArgumentParser(description="Run a single Craigslist crawl.")
    parser.add_argument("--region", default=DEFAULT_REGION, help="Craigslist region subdomain")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="SQLite database path")
    parser.add_argument("--webhook", default=None, help="Slack webhook URL (optional)")
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
    crawl_once(
        args.region,
        args.db_path,
        args.webhook,
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

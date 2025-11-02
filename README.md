# FreeFinder

FreeFinder is a small Python scraper that watches Craigslist's free-stuff feed, keeps the useful listings, and saves them in a local SQLite database. The codebase is intentionally tiny so you can read through it and understand the full flow in an afternoon.

## How the Project Works

1. **`cli.py`** is the main entry point. It builds a Craigslist search URL, checks `robots.txt`, fetches the results page, and coordinates every other module.
2. **`fetcher.py`** handles HTTP requests. It adds delays and browser-like headers so we behave politely toward Craigslist.
3. **`sites/craigslist.py`** parses the search page, opens each listing, and records the most recent activity (posted or updated time).
4. **`filters.py`** keeps only the listings that match our helpful keyword list and are newer than seven days.
5. **`storage/sqlite.py`** creates the database (if needed), upserts fresh listings, and removes anything older than a week.
6. **`notify/slack.py`** (optional) posts a short Slack message whenever new rows are added.

Every module now contains small inline comments so you can skim the files and understand the intention behind each step.

## Getting Started

```bash
# 1. Create and activate a virtual environment (only once).
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# 2. Install dependencies.
pip install -r requirements.txt  # or manually install requests + beautifulsoup4 + lxml

# 3. Run a dry crawl so nothing is written to disk yet.
.venv/bin/python cli.py --dry-run
```

During a dry run the script prints every kept listing plus the reason any other listing was dropped (stale date, no matching keywords, blocked terms, etc.).

## Running a Full Crawl

```bash
.venv/bin/python cli.py \
  --postal 78254 \
  --search-distance 30 \
  --max-items 120
```

Key flags you can tweak:

- `--dry-run` – skip database writes and just print results.
- `--max-items` – stop after this many listings (defaults to 120).
- `--detail-sleep MIN MAX` – control how slowly we fetch each listing page.
- `--allow-out-of-order` – keep crawling after the first stale listing (useful for debugging).
- `--webhook <url>` – post to Slack when new rows were added.

All filters and limits are applied before anything hits the database, so the DB only ever contains relevant, recent items.

## Slack Notifications (Optional)

1. In Slack, create an “Incoming Webhook” and copy the generated URL.
2. Run the crawler with `--webhook https://hooks.slack.com/...`.
3. The `notify/slack.py` helper sends a single-line summary when new rows are inserted.

No webhook? No problem—the helper simply skips the HTTP request.

## Cleaning Up Old Data

Every non-dry crawl calls `purge_stale_items` in `storage/sqlite.py`. This removes listings whose last activity (posted or updated date) is more than seven days old. You never have to manually prune the database.

## Helpful Tips

- Craigslist is strict about automated access. Give the crawler time between runs and keep the default delays unless you have a good reason to change them.
- If you run into a 403 “blocked” page, wait a little while or try again from a different network.
- All important behaviour is covered by docstrings and inline comments, so feel free to open any module and follow the flow.

Happy crawling! If you add new sources or extra filters, mimic the patterns already in `sites/craigslist.py` and `filters.py` so the rest of the pipeline continues to work smoothly.

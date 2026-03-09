"""
Collects Trump's Truth Social post counts via the public Mastodon-compatible API.

No API keys or authentication required for public profiles.
Two collection methods:
  1. Profile lookup — gets total statuses_count (exact, not rounded)
  2. Timeline scrape — counts individual posts per day (granular)
"""

import csv
import os
import json
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from database import insert_snapshot, get_last_snapshot, upsert_daily_count
from config import TRUTH_SOCIAL_ACCOUNT_ID, TRUTH_SOCIAL_API_BASE, TRUTH_SOCIAL_USERNAME

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "manual_counts.csv")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def api_get(endpoint: str, params: dict = None) -> dict | list | None:
    """Make a GET request to Truth Social's Mastodon API."""
    url = f"{TRUTH_SOCIAL_API_BASE}{endpoint}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except (URLError, HTTPError) as e:
        print(f"API error ({url}): {e}")
        return None


def fetch_total_post_count() -> int | None:
    """Get Trump's exact total post count from profile lookup."""
    data = api_get(f"/accounts/{TRUTH_SOCIAL_ACCOUNT_ID}")
    if data and "statuses_count" in data:
        count = data["statuses_count"]
        print(f"Total post count from API: {count:,}")
        return count
    print("Failed to fetch profile data")
    return None


def fetch_posts_since(since_id: str = None, limit: int = 40) -> list[dict]:
    """
    Fetch recent posts from Trump's timeline.
    Returns list of posts with id, created_at, content, etc.
    """
    params = {"limit": str(limit), "exclude_replies": "false"}
    if since_id:
        params["since_id"] = since_id

    data = api_get(f"/accounts/{TRUTH_SOCIAL_ACCOUNT_ID}/statuses", params)
    if data is None:
        return []
    return data


def count_posts_today() -> int:
    """Count how many posts Trump made today by paginating through the timeline."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    count = 0
    max_id = None

    for _ in range(10):  # Max 10 pages (400 posts) to prevent infinite loops
        params = {"limit": "40", "exclude_replies": "false"}
        if max_id:
            params["max_id"] = max_id

        posts = api_get(f"/accounts/{TRUTH_SOCIAL_ACCOUNT_ID}/statuses", params)
        if not posts:
            break

        for post in posts:
            post_date = post["created_at"][:10]  # "2026-03-09T..."
            if post_date == today:
                count += 1
            elif post_date < today:
                # We've gone past today, stop
                return count

        # Set up pagination
        if posts:
            max_id = posts[-1]["id"]
        else:
            break

    return count


def count_posts_by_date(target_date: str) -> int:
    """Count posts for a specific date (YYYY-MM-DD) by paginating the timeline."""
    count = 0
    max_id = None

    for _ in range(20):  # Max 20 pages
        params = {"limit": "40", "exclude_replies": "false"}
        if max_id:
            params["max_id"] = max_id

        posts = api_get(f"/accounts/{TRUTH_SOCIAL_ACCOUNT_ID}/statuses", params)
        if not posts:
            break

        for post in posts:
            post_date = post["created_at"][:10]
            if post_date == target_date:
                count += 1
            elif post_date < target_date:
                return count

        if posts:
            max_id = posts[-1]["id"]
        else:
            break

    return count


def collect_once() -> int | None:
    """
    Fetch current total count, compute delta, store snapshot and daily count.
    Also counts today's posts individually for granular daily data.
    """
    total = fetch_total_post_count()
    if total is None:
        print(f"[{datetime.utcnow().isoformat()}] Failed to fetch post count")
        return None

    last = get_last_snapshot()
    delta = 0
    if last:
        delta = max(0, total - last["total_tweets"])

    insert_snapshot(total, delta)

    # Also get granular daily count by counting individual posts
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_count = count_posts_today()
    if today_count > 0:
        # Use the actual counted posts rather than the delta
        upsert_daily_count(today, today_count, replace=True)
        print(f"[{datetime.utcnow().isoformat()}] Total: {total:,}, Today's posts: {today_count}")
    else:
        print(f"[{datetime.utcnow().isoformat()}] Total: {total:,}, Delta: +{delta}")
        if delta > 0:
            upsert_daily_count(today, delta)

    return today_count or delta


def backfill_daily_counts(days: int = 30, batch_size: int = 5, cooldown: int = 60):
    """
    Backfill daily post counts in batches to avoid 429 rate limits.

    Args:
        days: Total days of history to backfill.
        batch_size: Days to fetch per batch before pausing.
        cooldown: Seconds to wait between batches.
    """
    import time

    print(f"Backfilling {days} days in batches of {batch_size} days ({cooldown}s cooldown)...")
    today = datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    all_counts = {}
    max_id = None
    batch_start_date = None
    days_seen_in_batch = set()

    page = 0
    while page < 200:
        params = {"limit": "40", "exclude_replies": "false"}
        if max_id:
            params["max_id"] = max_id

        posts = api_get(f"/accounts/{TRUTH_SOCIAL_ACCOUNT_ID}/statuses", params)
        if not posts:
            break

        for post in posts:
            post_date = post["created_at"][:10]
            if post_date < cutoff:
                _store_backfill(all_counts)
                return all_counts

            all_counts[post_date] = all_counts.get(post_date, 0) + 1

            if batch_start_date is None:
                batch_start_date = post_date
            days_seen_in_batch.add(post_date)

        max_id = posts[-1]["id"]
        page += 1
        oldest = posts[-1]["created_at"][:10]
        print(f"  Page {page}: processed {len(posts)} posts (oldest: {oldest})")

        # Check if we've filled a batch worth of days
        if len(days_seen_in_batch) >= batch_size:
            _store_backfill(all_counts)
            print(f"  ✓ Batch done ({len(days_seen_in_batch)} days). Cooling down {cooldown}s...")
            days_seen_in_batch.clear()
            batch_start_date = None
            time.sleep(cooldown)

    _store_backfill(all_counts)
    return all_counts


def _store_backfill(counts_by_date: dict):
    """Store backfilled daily counts in the database."""
    for date_str, count in sorted(counts_by_date.items()):
        upsert_daily_count(date_str, count, replace=True)
    print(f"Backfilled {len(counts_by_date)} days of data")
    for date_str in sorted(counts_by_date.keys()):
        print(f"  {date_str}: {counts_by_date[date_str]} posts")


def fetch_post_count_csv() -> int | None:
    """Read the latest manually entered count from CSV fallback."""
    if not os.path.exists(CSV_PATH):
        return None
    try:
        with open(CSV_PATH, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                last = rows[-1]
                return int(last["total_posts"])
    except Exception as e:
        print(f"CSV read error: {e}")
    return None


def add_manual_count(total_posts: int):
    """Manually add a count to the CSV fallback file."""
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "total_posts"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.utcnow().isoformat(),
            "total_posts": total_posts,
        })
    print(f"Manually recorded: {total_posts:,} posts")

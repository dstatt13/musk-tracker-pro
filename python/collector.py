"""
Collects Trump's Truth Social post counts via the public Mastodon-compatible API.

No API keys or authentication required for public profiles.
Two collection methods:
  1. Profile lookup — gets total statuses_count (exact, not rounded)
  2. Timeline scrape — counts individual posts per day (granular)

Rate limiting:
  Truth Social's Mastodon API allows ~300 requests per 5 minutes per IP.
  The collector reads X-RateLimit-Remaining headers and pauses automatically.
"""

import csv
import os
import json
import time
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from database import insert_snapshot, get_last_snapshot, upsert_daily_count
from config import TRUTH_SOCIAL_ACCOUNT_ID, TRUTH_SOCIAL_API_BASE, TRUTH_SOCIAL_USERNAME, TRUTH_SOCIAL_TOKEN

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "manual_counts.csv")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Rate limit state
_rate_limit_remaining = None
_rate_limit_reset = None

RATE_LIMIT_BUFFER = 5        # Pause when this many requests remain
RATE_LIMIT_COOLDOWN = 300    # 5 minutes default cooldown


def _parse_rate_limit_headers(resp):
    """Read rate limit headers from response and update global state."""
    global _rate_limit_remaining, _rate_limit_reset

    remaining = resp.headers.get("X-RateLimit-Remaining")
    reset = resp.headers.get("X-RateLimit-Reset")

    if remaining is not None:
        _rate_limit_remaining = int(remaining)
    if reset is not None:
        _rate_limit_reset = reset

    return _rate_limit_remaining


def _wait_if_rate_limited():
    """Check rate limit state and sleep if we're close to the limit."""
    global _rate_limit_remaining, _rate_limit_reset

    if _rate_limit_remaining is not None and _rate_limit_remaining <= RATE_LIMIT_BUFFER:
        # Calculate wait time from reset header, or default to 5 min
        wait_seconds = RATE_LIMIT_COOLDOWN
        if _rate_limit_reset:
            try:
                # Mastodon returns ISO 8601 timestamp
                reset_time = datetime.fromisoformat(_rate_limit_reset.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                wait_seconds = max(10, int((reset_time - now).total_seconds()) + 5)
            except (ValueError, TypeError):
                pass

        print(f"  ⏳ Rate limit approaching ({_rate_limit_remaining} remaining). "
              f"Waiting {wait_seconds}s until reset...")
        time.sleep(wait_seconds)
        _rate_limit_remaining = None  # Reset after waiting


def api_get(endpoint: str, params: dict = None) -> dict | list | None:
    """Make a GET request to Truth Social's Mastodon API with rate limit awareness."""
    _wait_if_rate_limited()

    url = f"{TRUTH_SOCIAL_API_BASE}{endpoint}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=30) as resp:
            remaining = _parse_rate_limit_headers(resp)
            if remaining is not None:
                limit = resp.headers.get("X-RateLimit-Limit", "?")
                print(f"  [Rate limit: {remaining}/{limit} remaining]")
            return json.loads(resp.read().decode())
    except HTTPError as e:
        if e.code == 429:
            # Read retry info from error response
            retry_after = e.headers.get("Retry-After")
            reset = e.headers.get("X-RateLimit-Reset")
            wait = RATE_LIMIT_COOLDOWN

            if retry_after:
                wait = int(retry_after) + 5
            elif reset:
                try:
                    reset_time = datetime.fromisoformat(reset.replace("Z", "+00:00"))
                    wait = max(10, int((reset_time - datetime.now(timezone.utc)).total_seconds()) + 5)
                except (ValueError, TypeError):
                    pass

            print(f"  🚫 429 Too Many Requests. Waiting {wait}s...")
            time.sleep(wait)
            # Retry once after waiting
            try:
                with urlopen(req, timeout=30) as resp:
                    _parse_rate_limit_headers(resp)
                    return json.loads(resp.read().decode())
            except (URLError, HTTPError) as e2:
                print(f"  Retry failed: {e2}")
                return None
        else:
            print(f"API error ({url}): {e}")
            return None
    except URLError as e:
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

    for _ in range(10):
        params = {"limit": "40", "exclude_replies": "false"}
        if max_id:
            params["max_id"] = max_id

        posts = api_get(f"/accounts/{TRUTH_SOCIAL_ACCOUNT_ID}/statuses", params)
        if not posts:
            break

        for post in posts:
            post_date = post["created_at"][:10]
            if post_date == today:
                count += 1
            elif post_date < today:
                return count

        if posts:
            max_id = posts[-1]["id"]
        else:
            break

    return count


def count_posts_by_date(target_date: str) -> int:
    """Count posts for a specific date (YYYY-MM-DD) by paginating the timeline."""
    count = 0
    max_id = None

    for _ in range(20):
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
        upsert_daily_count(today, today_count, replace=True)
        print(f"[{datetime.utcnow().isoformat()}] Total: {total:,}, Today's posts: {today_count}")
    else:
        print(f"[{datetime.utcnow().isoformat()}] Total: {total:,}, Delta: +{delta}")
        if delta > 0:
            upsert_daily_count(today, delta)

    return today_count or delta


def backfill_daily_counts(days: int = 30):
    """
    Backfill daily post counts by paginating through the timeline history.
    Rate-limit-aware: reads X-RateLimit-Remaining and pauses automatically.
    Saves progress after each batch of days.
    """
    print(f"Backfilling {days} days (rate-limit-aware, auto-pausing)...")
    today = datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    all_counts = {}
    max_id = None
    last_saved_days = 0

    page = 0
    while page < 500:  # Safety limit
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

        max_id = posts[-1]["id"]
        page += 1
        oldest = posts[-1]["created_at"][:10]
        print(f"  Page {page}: {len(posts)} posts (oldest: {oldest}) "
              f"[{len(all_counts)} days collected]")

        # Save progress every 5 new days
        if len(all_counts) >= last_saved_days + 5:
            _store_backfill(all_counts)
            last_saved_days = len(all_counts)

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

"""
Collects Elon Musk's tweet count from the X API v2.

Uses the users/:id endpoint to get public_metrics.tweet_count.
This gives the total lifetime tweet count; we compute deltas locally.
"""

import requests
from datetime import datetime, timezone
from config import BEARER_TOKEN, ELON_USER_ID
from database import insert_snapshot, get_last_snapshot, upsert_daily_count


def fetch_tweet_count() -> int | None:
    """Fetch Elon's current total tweet count from X API v2."""
    url = f"https://api.x.com/2/users/{ELON_USER_ID}"
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    params = {"user.fields": "public_metrics"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["data"]["public_metrics"]["tweet_count"]
    except Exception as e:
        print(f"[{datetime.utcnow().isoformat()}] Error fetching tweet count: {e}")
        return None


def collect_once() -> int | None:
    """Fetch current count, compute delta, store snapshot and daily count."""
    total = fetch_tweet_count()
    if total is None:
        return None

    last = get_last_snapshot()
    delta = 0
    if last:
        delta = max(0, total - last["total_tweets"])  # handle edge cases

    insert_snapshot(total, delta)

    if delta > 0:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        upsert_daily_count(today, delta)

    print(f"[{datetime.utcnow().isoformat()}] Total: {total}, Delta: +{delta}")
    return delta

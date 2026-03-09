"""
Collects Elon Musk's tweet count by scraping x.com profile with Playwright.

Falls back to a manual CSV if scraping fails.
After first install, run: playwright install chromium
"""

import re
import csv
import os
from datetime import datetime, timezone
from database import insert_snapshot, get_last_snapshot, upsert_daily_count

ELON_PROFILE_URL = "https://x.com/elonmusk"
CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "manual_counts.csv")


def parse_count(text: str) -> int | None:
    """Parse '45.2K posts' or '45,231 posts' into an integer."""
    text = text.strip().lower().replace(",", "")
    match = re.search(r"([\d.]+)\s*([kmb]?)", text)
    if not match:
        return None
    num = float(match.group(1))
    suffix = match.group(2)
    multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(suffix, 1)
    return int(num * multiplier)


def fetch_tweet_count_playwright() -> int | None:
    """Scrape Elon's total post count from x.com using Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto(ELON_PROFILE_URL, wait_until="networkidle", timeout=30000)

            # Wait for profile to load
            page.wait_for_timeout(3000)

            # Try multiple selectors for the posts count
            # X shows it as "XX.XK posts" in the profile header area
            selectors = [
                'a[href="/elonmusk"] span',  # Direct link to posts
                '[data-testid="UserProfileHeader_Items"]',
                'h2[role="heading"]',
            ]

            html = page.content()
            browser.close()

            # Search for post count pattern in full HTML
            # Patterns: "42,567 posts", "42.5K posts", etc.
            patterns = [
                r'([\d,]+)\s*(?:posts|Posts)',
                r'([\d.]+[KkMm])\s*(?:posts|Posts)',
            ]

            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    count = parse_count(match.group(1) + " posts")
                    if count and count > 10_000:  # Elon has way more than 10K
                        print(f"Scraped tweet count: {count:,}")
                        return count

            print("Could not find post count in page HTML")
            return None

    except Exception as e:
        print(f"Playwright scraping error: {e}")
        return None


def fetch_tweet_count_csv() -> int | None:
    """Read the latest manually entered count from CSV fallback."""
    if not os.path.exists(CSV_PATH):
        return None
    try:
        with open(CSV_PATH, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                last = rows[-1]
                return int(last["total_tweets"])
    except Exception as e:
        print(f"CSV read error: {e}")
    return None


def fetch_tweet_count() -> int | None:
    """Try Playwright first, fall back to CSV."""
    count = fetch_tweet_count_playwright()
    if count is None:
        print("Playwright failed, trying CSV fallback...")
        count = fetch_tweet_count_csv()
    return count


def collect_once() -> int | None:
    """Fetch current count, compute delta, store snapshot and daily count."""
    total = fetch_tweet_count()
    if total is None:
        print(f"[{datetime.utcnow().isoformat()}] Failed to fetch tweet count")
        return None

    last = get_last_snapshot()
    delta = 0
    if last:
        delta = max(0, total - last["total_tweets"])

    insert_snapshot(total, delta)

    if delta > 0:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        upsert_daily_count(today, delta)

    print(f"[{datetime.utcnow().isoformat()}] Total: {total:,}, Delta: +{delta}")
    return delta


def add_manual_count(total_tweets: int):
    """Manually add a count to the CSV fallback file."""
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "total_tweets"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.utcnow().isoformat(),
            "total_tweets": total_tweets,
        })
    print(f"Manually recorded: {total_tweets:,} tweets")

#!/usr/bin/env python3
"""
Trump Truth Social Post Tracker & Predictor
=============================================
Runs 24/7 collecting post counts via Truth Social's public API and periodically retraining predictions.

Usage:
  1. pip install -r requirements.txt
  2. python main.py

Options:
  --collect-only    Only collect data, don't run predictions
  --predict-only    Only run predictions on existing data
  --threshold N D   Probability of ≥N posts in D days (Polymarket helper)
  --backfill [N]    Backfill daily counts from timeline history (default 30 days)
  --manual COUNT    Manually record a total post count (fallback)
"""

import sys
import time
import signal
import schedule
from datetime import datetime, timezone

from config import POLL_INTERVAL_MINUTES
from database import init_db, get_daily_counts
from collector import collect_once, add_manual_count, backfill_daily_counts
from model import run_predictions, train_hmm, get_current_state, predict_polymarket_threshold, STATE_LABELS

running = True


def signal_handler(sig, frame):
    global running
    print("\nShutting down gracefully...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def collection_job():
    print(f"\n[{datetime.now(timezone.utc).isoformat()}] Running collection...")
    collect_once()


def prediction_job():
    print(f"\n[{datetime.now(timezone.utc).isoformat()}] Running predictions...")
    run_predictions()


def polymarket_query(threshold: int, window_days: int):
    """One-off Polymarket probability query."""
    rows = get_daily_counts()
    if not rows or len(rows) < 14:
        print(f"Need ≥14 days of data (have {len(rows)}). Collect more first.")
        return

    daily_counts = [r["tweet_count"] for r in rows]
    model = train_hmm(daily_counts)
    if model is None:
        return

    current_state = get_current_state(model, daily_counts)
    prob = predict_polymarket_threshold(model, current_state, window_days, threshold)

    print(f"\n{'='*60}")
    print(f"POLYMARKET QUERY")
    print(f"{'='*60}")
    print(f"Question: Will Trump post ≥{threshold} times in {window_days} days?")
    print(f"Current state: {STATE_LABELS[current_state]}")
    print(f"Estimated probability: {prob*100:.1f}%")
    print(f"{'='*60}")

    if prob > 0.65:
        print("→ Signal: STRONG YES — consider buying YES shares")
    elif prob > 0.55:
        print("→ Signal: LEAN YES — moderate confidence")
    elif prob > 0.45:
        print("→ Signal: COIN FLIP — no edge, avoid")
    elif prob > 0.35:
        print("→ Signal: LEAN NO — moderate confidence")
    else:
        print("→ Signal: STRONG NO — consider buying NO shares")


def main():
    init_db()

    # Handle --manual flag
    if "--manual" in sys.argv:
        try:
            idx = sys.argv.index("--manual")
            count = int(sys.argv[idx + 1])
            add_manual_count(count)
        except (IndexError, ValueError):
            print("Usage: python main.py --manual <total_post_count>")
            print("Example: python main.py --manual 32567")
        return

    # Handle --backfill flag
    if "--backfill" in sys.argv:
        try:
            idx = sys.argv.index("--backfill")
            days = int(sys.argv[idx + 1]) if len(sys.argv) > idx + 1 and sys.argv[idx + 1].isdigit() else 30
            backfill_daily_counts(days)
        except Exception as e:
            print(f"Backfill error: {e}")
        return

    if "--predict-only" in sys.argv:
        run_predictions()
        return

    if "--threshold" in sys.argv:
        try:
            idx = sys.argv.index("--threshold")
            threshold = int(sys.argv[idx + 1])
            window = int(sys.argv[idx + 2])
            polymarket_query(threshold, window)
        except (IndexError, ValueError):
            print("Usage: python main.py --threshold <min_posts> <days>")
            print("Example: python main.py --threshold 50 7")
        return

    if "--range" in sys.argv:
        try:
            from model import predict_date_range
            idx = sys.argv.index("--range")
            start_date = sys.argv[idx + 1]
            end_date = sys.argv[idx + 2]
            threshold = None
            if len(sys.argv) > idx + 3 and sys.argv[idx + 3].isdigit():
                threshold = int(sys.argv[idx + 3])
            predict_date_range(start_date, end_date, threshold)
        except (IndexError, ValueError):
            print("Usage: python main.py --range <start_date> <end_date> [threshold]")
            print("Example: python main.py --range 2026-03-09 2026-03-12")
            print("Example: python main.py --range 2026-03-09 2026-03-12 50")
        return

    collect_only = "--collect-only" in sys.argv

    # Initial collection
    print("Starting Trump Truth Social Post Tracker...")
    print(f"Polling every {POLL_INTERVAL_MINUTES} minutes")
    print("Using Truth Social public Mastodon API (no API key needed)")
    collect_once()

    # Schedule jobs
    schedule.every(POLL_INTERVAL_MINUTES).minutes.do(collection_job)
    if not collect_only:
        schedule.every(6).hours.do(prediction_job)
        rows = get_daily_counts()
        if len(rows) >= 14:
            prediction_job()
        else:
            print(f"Need ≥14 days of data for predictions (have {len(rows)})")
            print("TIP: Run 'python main.py --backfill 30' to instantly get ~30 days of data")

    # Main loop
    while running:
        schedule.run_pending()
        time.sleep(10)

    print("Stopped.")


if __name__ == "__main__":
    main()

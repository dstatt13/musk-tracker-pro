#!/usr/bin/env python3
"""
Elon Musk Tweet Tracker & Predictor
====================================
Runs 24/7 collecting tweet counts and periodically retraining predictions.

Usage:
  1. Create python/.env with: X_BEARER_TOKEN=your_token
  2. pip install -r requirements.txt
  3. python main.py

Options:
  --collect-only    Only collect data, don't run predictions
  --predict-only    Only run predictions on existing data
  --threshold N D   Probability of ≥N tweets in D days (Polymarket helper)
"""

import sys
import time
import signal
import schedule
from datetime import datetime

from config import POLL_INTERVAL_MINUTES, BEARER_TOKEN
from database import init_db, get_daily_counts
from collector import collect_once
from model import run_predictions, train_hmm, get_current_state, predict_polymarket_threshold, STATE_LABELS

running = True


def signal_handler(sig, frame):
    global running
    print("\nShutting down gracefully...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def collection_job():
    print(f"\n[{datetime.utcnow().isoformat()}] Running collection...")
    collect_once()


def prediction_job():
    print(f"\n[{datetime.utcnow().isoformat()}] Running predictions...")
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
    print(f"Question: Will Elon tweet ≥{threshold} times in {window_days} days?")
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
    if not BEARER_TOKEN:
        print("ERROR: X_BEARER_TOKEN not set.")
        print("Create python/.env with: X_BEARER_TOKEN=your_bearer_token")
        print("\nGet one at: https://developer.x.com/en/portal/dashboard")
        sys.exit(1)

    init_db()

    # Handle CLI arguments
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
            print("Usage: python main.py --threshold <min_tweets> <days>")
            print("Example: python main.py --threshold 50 7")
        return

    collect_only = "--collect-only" in sys.argv

    # Initial collection
    print("Starting Elon Musk Tweet Tracker...")
    print(f"Polling every {POLL_INTERVAL_MINUTES} minutes")
    collect_once()

    # Schedule jobs
    schedule.every(POLL_INTERVAL_MINUTES).minutes.do(collection_job)
    if not collect_only:
        schedule.every(6).hours.do(prediction_job)
        # Run initial prediction if we have enough data
        rows = get_daily_counts()
        if len(rows) >= 14:
            prediction_job()
        else:
            print(f"Need ≥14 days of data for predictions (have {len(rows)})")

    # Main loop
    while running:
        schedule.run_pending()
        time.sleep(10)

    print("Stopped.")


if __name__ == "__main__":
    main()

"""SQLite database for storing post count snapshots."""

import sqlite3
import os
from datetime import datetime
from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tweet_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total_tweets INTEGER NOT NULL,
            delta_since_last INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_counts (
            date TEXT PRIMARY KEY,
            tweet_count INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at TEXT NOT NULL,
            window_days INTEGER NOT NULL,
            predicted_mean REAL NOT NULL,
            predicted_median REAL NOT NULL,
            ci_lower_5 REAL NOT NULL,
            ci_upper_95 REAL NOT NULL,
            current_state INTEGER NOT NULL,
            state_label TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def insert_snapshot(total_tweets: int, delta: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO tweet_snapshots (timestamp, total_tweets, delta_since_last) VALUES (?, ?, ?)",
        (datetime.utcnow().isoformat(), total_tweets, delta),
    )
    conn.commit()
    conn.close()


def get_last_snapshot() -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM tweet_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_daily_count(date_str: str, count: int, replace: bool = False):
    conn = get_connection()
    if replace:
        conn.execute(
            "INSERT INTO daily_counts (date, tweet_count) VALUES (?, ?) "
            "ON CONFLICT(date) DO UPDATE SET tweet_count = ?",
            (date_str, count, count),
        )
    else:
        conn.execute(
            "INSERT INTO daily_counts (date, tweet_count) VALUES (?, ?) "
            "ON CONFLICT(date) DO UPDATE SET tweet_count = tweet_count + ?",
            (date_str, count, count),
        )
    conn.commit()
    conn.close()


def get_daily_counts() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM daily_counts ORDER BY date ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_prediction(window_days: int, mean: float, median: float,
                       ci_lower: float, ci_upper: float,
                       state: int, state_label: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO predictions (generated_at, window_days, predicted_mean, predicted_median, "
        "ci_lower_5, ci_upper_95, current_state, state_label) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), window_days, mean, median, ci_lower, ci_upper, state, state_label),
    )
    conn.commit()
    conn.close()

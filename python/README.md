# Trump Truth Social Post Predictor

A Hidden Markov Model + Monte Carlo simulation tool for predicting Donald Trump's Truth Social posting activity. Designed for Polymarket betting on "Will Trump post X times in Y days?" markets.

**No API keys required** — uses Truth Social's public Mastodon-compatible API.

---

## Quick Start

```bash
cd python
pip install -r requirements.txt
python main.py --backfill 30   # Instantly load ~30 days of history
python main.py                  # Start 24/7 tracker
```

---

## Commands Reference

### Data Collection

| Command | Description |
|---------|-------------|
| `python main.py` | Start 24/7 collector + auto-predictions (after 14 days) |
| `python main.py --collect-only` | Collect data only, no predictions |
| `python main.py --backfill [N]` | Backfill N days of history from timeline (default 30) |
| `python main.py --manual <count>` | Manually record a total post count |

### Predictions

| Command | Description |
|---------|-------------|
| `python main.py --predict-only` | Run predictions on existing data (1, 3, 7, 14, 30 day forecasts) |
| `python main.py --range <start> <end>` | Predict posts for a specific date range |
| `python main.py --range <start> <end> <threshold>` | Same + probability of hitting ≥threshold posts |
| `python main.py --threshold <min_posts> <days>` | Polymarket query: probability of ≥N posts in D days |

---

## Command Details & Examples

### `python main.py` — 24/7 Collector

Polls Trump's post count every 30 minutes via the Truth Social API, stores in SQLite. Predictions auto-activate after 14+ days of data.

```bash
python main.py
# Starting Trump Truth Social Post Tracker...
# Polling every 30 minutes
# Using Truth Social public Mastodon API (no API key needed)
```

Press `Ctrl+C` to stop gracefully. All data is persisted in `data/posts.db`.

---

### `python main.py --backfill [N]` — Instant History

Paginates through Trump's timeline to backfill daily post counts. **Run this first** to skip the 14-day data collection wait.

```bash
python main.py --backfill 30
# Backfilling daily counts for the last 30 days...
#   Page 1: processed 40 posts (oldest: 2026-03-08)
#   Page 2: processed 40 posts (oldest: 2026-03-06)
#   ...
# Backfilled 30 days of data
#   2026-02-07: 12 posts
#   2026-02-08: 8 posts
#   ...
```

---

### `python main.py --predict-only` — Standard Predictions

Outputs forecasts for 1, 3, 7, 14, and 30 days ahead. Requires ≥14 days of collected data.

```bash
python main.py --predict-only
```

**Output includes:**
- HMM model summary (current state, state means, transition matrix)
- Per-window forecasts: mean, median, 90% confidence interval, P(>0)

```
7-day forecast:
  Mean:   48.3 posts
  Median: 46.0 posts
  90% CI: [18, 82]
  P(>0):  100.0%
```

---

### `python main.py --range <start_date> <end_date> [threshold]`

Predict total posts for a specific future date range.

```bash
python main.py --range 2026-03-09 2026-03-12
python main.py --range 2026-03-09 2026-03-12 50
```

---

### `python main.py --threshold <min_posts> <days>` — Polymarket Query

Directly answers "Will Trump post ≥N times in D days?" with a probability and trading signal.

```bash
python main.py --threshold 50 7
```

**Output:**
```
POLYMARKET QUERY
============================================================
Question: Will Trump post ≥50 times in 7 days?
Current state: Medium
Estimated probability: 72.3%
============================================================
→ Signal: STRONG YES — consider buying YES shares
```

**Signal guide:**

| Probability | Signal | Action |
|-------------|--------|--------|
| >65% | STRONG YES | Buy YES shares |
| 55-65% | LEAN YES | Moderate confidence |
| 45-55% | COIN FLIP | No edge, avoid |
| 35-45% | LEAN NO | Moderate confidence |
| <35% | STRONG NO | Buy NO shares |

---

## How It Works

### 1. Data Collection
- Calls Truth Social's public Mastodon-compatible API (no auth needed)
- Gets exact total post count from profile endpoint
- Counts individual posts per day from the timeline endpoint
- Stores snapshots + daily aggregates in SQLite

### 2. Hidden Markov Model (HMM)
Learns 3 behavioral "states" from historical daily post counts:

| State | Description |
|-------|-------------|
| **Low** | Minimal posting (quiet days, travel, etc.) |
| **Medium** | Baseline activity |
| **High** | Post storms (major news, rallies, controversies) |

### 3. Monte Carlo Simulation
For predictions:
1. Identify current state via Viterbi decoding
2. Run 10,000 simulated futures
3. Aggregate simulations into probability distributions

---

## Data Storage

| File | Description |
|------|-------------|
| `data/posts.db` | SQLite database (snapshots, daily counts, predictions) |
| `data/manual_counts.csv` | Fallback manual entries |

---

## Configuration

Edit `config.py` or create a `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `POLL_INTERVAL_MINUTES` | 30 | How often to poll the API |
| `N_HIDDEN_STATES` | 3 | HMM states (Low/Medium/High) |
| `N_SIMULATIONS` | 10,000 | Monte Carlo runs |

---

## Key Advantage Over X/Twitter

Truth Social is built on Mastodon, which provides a **public API with exact post counts** — no rounding, no API keys, no rate limit issues. This gives us granular daily data (single-digit accuracy) compared to X's rounded "98.7K posts" display.

---

## Files

```
python/
├── main.py          # CLI entry point
├── collector.py     # Truth Social API collector
├── model.py         # HMM training + Monte Carlo predictions
├── database.py      # SQLite schema & queries
├── config.py        # Configuration constants
├── requirements.txt # Python dependencies
└── data/
    ├── posts.db             # SQLite database (auto-created)
    └── manual_counts.csv    # Fallback manual entries
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Need ≥14 days of data" | Run `python main.py --backfill 30` to instantly load history |
| API returns empty data | Truth Social may be rate-limiting; wait a few minutes and retry |
| "Failed to fetch post count" | Check internet connection; Truth Social API may be temporarily down |

---

## Tips for Polymarket

1. **Check current state first** — High state → expect more posts
2. **Use date ranges for specific markets** — Match the market's exact window
3. **Backfill before predicting** — Run `--backfill 60` for better model accuracy
4. **Look at the distribution** — A 50% probability with tight CI differs from 50% with huge variance
5. **Don't bet on coin flips** — Only trade when probability is >60% or <40%

---

## License

MIT — use at your own risk. This is for educational/entertainment purposes. Gambling involves risk of loss.

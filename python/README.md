# Elon Musk Tweet Predictor

A Hidden Markov Model + Monte Carlo simulation tool for predicting Elon Musk's X (Twitter) posting activity. Designed for Polymarket betting on "Will Elon Musk tweet X times in Y days?" markets.

**No API keys required** — uses Playwright to scrape x.com directly.

---

## Quick Start

```bash
cd python
pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

This starts the 24/7 collector. Let it run for ~14 days to gather enough data for predictions.

---

## Commands Reference

### Data Collection

| Command | Description |
|---------|-------------|
| `python main.py` | Start 24/7 collector + auto-predictions (after 14 days) |
| `python main.py --collect-only` | Collect data only, no predictions |
| `python main.py --manual <count>` | Manually record a total tweet count |

### Predictions

| Command | Description |
|---------|-------------|
| `python main.py --predict-only` | Run predictions on existing data (1, 3, 7, 14, 30 day forecasts) |
| `python main.py --range <start> <end>` | Predict tweets for a specific date range |
| `python main.py --range <start> <end> <threshold>` | Same + probability of hitting ≥threshold tweets |
| `python main.py --threshold <min_tweets> <days>` | Polymarket query: probability of ≥N tweets in D days |

---

## Command Details & Examples

### `python main.py` — 24/7 Collector

Scrapes Elon's tweet count every hour, stores in SQLite. Predictions auto-activate after 14+ days of data.

```bash
python main.py
# Starting Elon Musk Tweet Tracker...
# Polling every 60 minutes
# Using Playwright web scraper (no API key needed)
```

Press `Ctrl+C` to stop gracefully. All data is persisted in `data/tweets.db`.

---

### `python main.py --collect-only` — Collect Without Predictions

Same as default, but skips the prediction phase entirely. Useful when you just want to accumulate data.

```bash
python main.py --collect-only
```

---

### `python main.py --manual <count>` — Manual Count Entry

Fallback when scraping fails (e.g., X blocks the request). Find the count on Elon's profile page (`x.com/elonmusk`).

```bash
python main.py --manual 42567
# Manually recorded: 42,567 tweets
```

Entries are saved to `data/manual_counts.csv` and also processed through the normal pipeline.

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
  Mean:   48.3 tweets
  Median: 46.0 tweets
  90% CI: [18, 82]
  P(>0):  100.0%
```

---

### `python main.py --range <start_date> <end_date> [threshold]` — Date Range Prediction

Predict total tweets for a specific future date range. Accounts for uncertainty by simulating "lead days" between now and the start date.

```bash
# Predict tweets from March 9-12, 2026
python main.py --range 2026-03-09 2026-03-12

# Same, but also check probability of ≥50 tweets
python main.py --range 2026-03-09 2026-03-12 50
```

**Output includes:**
- Summary stats (mean, median, 90% CI)
- Probability breakdown by range:
  ```
  PROBABILITY BREAKDOWN BY RANGE
  ============================================================
         0-20:   5.2%  ██
        20-40:  18.3%  ███████
        40-60:  31.7%  ████████████
        60-80:  26.4%  ██████████
       80-100:  12.8%  █████
      100-120:   4.1%  █
  ```
- Threshold probability with trading signal (if threshold provided)

---

### `python main.py --threshold <min_tweets> <days>` — Polymarket Query

Directly answers "Will Elon tweet ≥N times in D days?" with a probability and trading signal.

```bash
# "Will Elon tweet ≥50 times in the next 7 days?"
python main.py --threshold 50 7

# "Will Elon tweet ≥10 times tomorrow?"
python main.py --threshold 10 1
```

**Output:**
```
POLYMARKET QUERY
============================================================
Question: Will Elon tweet ≥50 times in 7 days?
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
- Playwright loads `x.com/elonmusk` in a headless browser
- Extracts total post count from profile
- Computes delta since last check
- Stores hourly snapshots + daily aggregates in SQLite

### 2. Hidden Markov Model (HMM)
Learns 3 behavioral "states" from historical daily tweet counts:

| State | Description |
|-------|-------------|
| **Low** | Minimal tweeting (busy with SpaceX/Tesla, traveling, etc.) |
| **Medium** | Baseline activity |
| **High** | Tweet storms (controversy, product launch, meme spree) |

The model learns:
- **Emission distributions**: How many tweets per day in each state (Gaussian)
- **Transition probabilities**: Likelihood of switching states day-to-day

### 3. Monte Carlo Simulation
For predictions:
1. Identify current state via Viterbi decoding
2. Run 10,000 simulated futures
3. Aggregate simulations into probability distributions

---

## Data Storage

All data persists locally between runs:

| File | Description |
|------|-------------|
| `data/tweets.db` | SQLite database (snapshots, daily counts, predictions) |
| `data/manual_counts.csv` | Fallback manual entries |

---

## Configuration

Edit `config.py` or create a `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `POLL_INTERVAL_MINUTES` | 60 | How often to scrape |
| `N_HIDDEN_STATES` | 3 | HMM states (Low/Medium/High) |
| `N_SIMULATIONS` | 10,000 | Monte Carlo runs |

---

## Files

```
python/
├── main.py          # CLI entry point
├── collector.py     # Playwright scraper + data collection
├── model.py         # HMM training + Monte Carlo predictions
├── database.py      # SQLite schema & queries
├── config.py        # Configuration constants
├── requirements.txt # Python dependencies
└── data/
    ├── tweets.db           # SQLite database (auto-created)
    └── manual_counts.csv   # Fallback manual entries
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Playwright not installed" | `pip install playwright && python -m playwright install chromium` |
| "Could not find post count in page HTML" | X changed layout — use `--manual <count>` as fallback |
| "Need ≥14 days of data" | Keep the collector running; HMM needs 2+ weeks to train |
| Timeout errors | Expected — X streams data continuously; the scraper uses `domcontentloaded` to avoid this |

---

## Tips for Polymarket

1. **Check current state first** — High state → expect more tweets
2. **Use date ranges for specific markets** — Match the market's exact window
3. **Consider lead time** — Predictions further out have wider confidence intervals
4. **Look at the distribution** — A 50% probability with tight CI is different from 50% with huge variance
5. **Don't bet on coin flips** — Only trade when probability is >60% or <40%

---

## License

MIT — use at your own risk. This is for educational/entertainment purposes. Gambling involves risk of loss.

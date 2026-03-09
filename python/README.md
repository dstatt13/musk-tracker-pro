# Elon Musk Tweet Predictor

HMM + Monte Carlo prediction model for Elon Musk's X posting activity, designed for Polymarket betting.

**No API keys required** — uses Playwright to scrape x.com directly.

## Setup

```bash
cd python
pip install -r requirements.txt
playwright install chromium
```

## Usage

### Run 24/7 collector + predictor
```bash
python main.py
```

### Collect data only
```bash
python main.py --collect-only
```

### Run predictions on existing data
```bash
python main.py --predict-only
```

### Polymarket query
```bash
# "Will Elon tweet ≥50 times in 7 days?"
python main.py --threshold 50 7
```

### Manual count entry (fallback if scraping fails)
```bash
python main.py --manual 42567
```

## How it Works

1. **Data Collection**: Scrapes x.com/elonmusk every hour for total post count, computes deltas, stores in SQLite
2. **Hidden Markov Model**: Learns 3 behavioral states (Low/Medium/High activity) with transition probabilities
3. **Monte Carlo Simulation**: 10,000 simulated futures from current state → probabilistic forecasts
4. **Polymarket Signals**: Probability estimates for "Will Elon tweet ≥X times in Y days?" markets

## Architecture

```
collector.py  → Playwright scraper → SQLite (tweet_snapshots, daily_counts)
model.py      → HMM training → Monte Carlo → predictions table
main.py       → Orchestrator (scheduler, CLI)
database.py   → SQLite schema & queries
config.py     → Configuration
```

## Notes

- Needs ~14 days of data before predictions are meaningful
- If Playwright scraping breaks (X changes layout), use `--manual` to keep feeding data
- Adjust `POLL_INTERVAL_MINUTES` in `.env` if needed (default: 60)

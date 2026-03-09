# Elon Musk Tweet Predictor

HMM + Monte Carlo prediction model for Elon Musk's X (Twitter) posting activity, designed for Polymarket betting.

## How it Works

1. **Data Collection**: Polls X API every hour for Elon's total tweet count, computes deltas, stores daily counts in SQLite
2. **Hidden Markov Model**: Learns 3 behavioral states (Low/Medium/High activity) and transition probabilities between them
3. **Monte Carlo Simulation**: Runs 10,000 simulated futures from the current state to predict tweet counts over various windows
4. **Polymarket Signals**: Translates predictions into probability estimates for "Will Elon tweet ≥X times in Y days?" style markets

## Setup

```bash
cd python
pip install -r requirements.txt
```

Create `.env` file:
```
X_BEARER_TOKEN=your_bearer_token_here
```

Get a Bearer Token at: https://developer.x.com/en/portal/dashboard

## Usage

### Run 24/7 collector + predictor
```bash
python main.py
```

### Collect data only (no predictions)
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

# "Will Elon tweet ≥10 times in 1 day?"
python main.py --threshold 10 1
```

## Architecture

```
collector.py  → X API polling → SQLite (tweet_snapshots, daily_counts)
model.py      → HMM training → Monte Carlo → predictions table
main.py       → Orchestrator (scheduler, CLI interface)
database.py   → SQLite schema & queries
config.py     → All configuration + .env loading
```

## Model Details

- **States**: 3 Gaussian-emission states sorted by mean activity level
- **Training**: Expectation-Maximization via `hmmlearn`
- **Prediction**: Forward-simulate state transitions + emission sampling
- **Confidence**: 90% credible intervals from simulation distribution

## Notes

- Needs ~14 days of hourly data collection before predictions are meaningful
- The model improves as more data accumulates
- Free X API tier supports user lookup; check rate limits at https://developer.x.com
- State labels (Low/Medium/High) are relative to observed data distribution

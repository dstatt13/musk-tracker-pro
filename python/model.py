"""
Hidden Markov Model + Monte Carlo simulation for tweet count prediction.

States represent Elon's tweeting "regimes":
  - State 0: Low activity (e.g., busy with SpaceX/Tesla, less tweeting)
  - State 1: Medium activity (normal baseline)
  - State 2: High activity (controversy, product launch, meme spree)

The HMM learns transition probabilities between these states and emission
distributions (how many tweets per day in each state). Monte Carlo then
simulates many possible futures to produce probabilistic forecasts.
"""

import numpy as np
from hmmlearn import hmm
from database import get_daily_counts, insert_prediction
from config import N_HIDDEN_STATES, N_SIMULATIONS, DEFAULT_PREDICTION_WINDOWS

STATE_LABELS = {0: "Low", 1: "Medium", 2: "High"}


def train_hmm(daily_counts: list[int]) -> hmm.GaussianHMM | None:
    """Train a Gaussian HMM on daily tweet counts."""
    if len(daily_counts) < 14:
        print(f"Need at least 14 days of data to train HMM (have {len(daily_counts)})")
        return None

    X = np.array(daily_counts).reshape(-1, 1).astype(float)

    model = hmm.GaussianHMM(
        n_components=N_HIDDEN_STATES,
        covariance_type="diag",
        n_iter=200,
        random_state=42,
        init_params="stmc",  # initialize all params
    )

    model.fit(X)

    # Sort states by mean emission (so state 0 = lowest activity)
    means = model.means_.flatten()
    order = np.argsort(means)
    model.means_ = model.means_[order]
    model.covars_ = model.covars_[order]
    model.transmat_ = model.transmat_[np.ix_(order, order)]
    model.startprob_ = model.startprob_[order]

    return model


def get_current_state(model: hmm.GaussianHMM, daily_counts: list[int]) -> int:
    """Decode the most likely current state using Viterbi algorithm."""
    X = np.array(daily_counts).reshape(-1, 1).astype(float)
    _, states = model.decode(X, algorithm="viterbi")
    return int(states[-1])


def monte_carlo_predict(
    model: hmm.GaussianHMM,
    current_state: int,
    window_days: int,
    n_simulations: int = N_SIMULATIONS,
) -> dict:
    """
    Run Monte Carlo simulation to predict total tweets over a window.

    For each simulation:
    1. Start from current_state
    2. For each day in window, sample next state from transition matrix
    3. Sample daily tweet count from that state's emission distribution
    4. Sum up total tweets for the window

    Returns statistics over all simulations.
    """
    totals = np.zeros(n_simulations)
    trans = model.transmat_
    means = model.means_.flatten()
    stds = np.sqrt(model.covars_.flatten())

    for sim in range(n_simulations):
        state = current_state
        total = 0.0
        for day in range(window_days):
            # Sample daily count from current state's Gaussian (floor at 0)
            daily = max(0, np.random.normal(means[state], stds[state]))
            total += daily
            # Transition to next state
            state = np.random.choice(N_HIDDEN_STATES, p=trans[state])
        totals[sim] = total

    return {
        "mean": float(np.mean(totals)),
        "median": float(np.median(totals)),
        "std": float(np.std(totals)),
        "ci_5": float(np.percentile(totals, 5)),
        "ci_95": float(np.percentile(totals, 95)),
        "ci_25": float(np.percentile(totals, 25)),
        "ci_75": float(np.percentile(totals, 75)),
        "min": float(np.min(totals)),
        "max": float(np.max(totals)),
        "prob_gt_0": float(np.mean(totals > 0)),
        "distribution": totals,
    }


def run_predictions() -> list[dict] | None:
    """Train model on all available data and generate predictions."""
    rows = get_daily_counts()
    if not rows:
        print("No daily count data available yet.")
        return None

    daily_counts = [r["tweet_count"] for r in rows]
    dates = [r["date"] for r in rows]

    model = train_hmm(daily_counts)
    if model is None:
        return None

    current_state = get_current_state(model, daily_counts)
    state_label = STATE_LABELS.get(current_state, "Unknown")

    print(f"\n{'='*60}")
    print(f"HMM Model Summary")
    print(f"{'='*60}")
    print(f"Training data: {len(daily_counts)} days ({dates[0]} to {dates[-1]})")
    print(f"Current state: {state_label} (state {current_state})")
    print(f"State means: {model.means_.flatten().round(1)}")
    print(f"Transition matrix:\n{model.transmat_.round(3)}")

    results = []
    print(f"\n{'='*60}")
    print(f"Predictions (Monte Carlo, {N_SIMULATIONS:,} simulations)")
    print(f"{'='*60}")

    for window in DEFAULT_PREDICTION_WINDOWS:
        pred = monte_carlo_predict(model, current_state, window)

        insert_prediction(
            window_days=window,
            mean=pred["mean"],
            median=pred["median"],
            ci_lower=pred["ci_5"],
            ci_upper=pred["ci_95"],
            state=current_state,
            state_label=state_label,
        )

        print(f"\n{window}-day forecast:")
        print(f"  Mean:   {pred['mean']:.1f} tweets")
        print(f"  Median: {pred['median']:.1f} tweets")
        print(f"  90% CI: [{pred['ci_5']:.0f}, {pred['ci_95']:.0f}]")
        print(f"  P(>0):  {pred['prob_gt_0']*100:.1f}%")

        results.append({"window_days": window, **pred})

    return results


def predict_polymarket_threshold(
    model: hmm.GaussianHMM,
    current_state: int,
    window_days: int,
    threshold: int,
) -> float:
    """
    Probability that Elon tweets >= threshold times in window_days.
    This directly answers Polymarket-style questions.
    """
    pred = monte_carlo_predict(model, current_state, window_days)
    prob = float(np.mean(pred["distribution"] >= threshold))
    return prob

"""
Configuration for the Trump Truth Social post tracker and predictor.

No API keys required! Uses Truth Social's public Mastodon-compatible API.
Optional: create a .env file for any overrides.
"""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Trump's Truth Social profile
TRUTH_SOCIAL_ACCOUNT_ID = "107780257626128497"
TRUTH_SOCIAL_USERNAME = "realDonaldTrump"
TRUTH_SOCIAL_API_BASE = "https://truthsocial.com/api/v1"

# Data collection
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "30"))
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "posts.db")

# HMM Model
N_HIDDEN_STATES = 3  # Low, Medium, High activity states
N_SIMULATIONS = 10_000  # Monte Carlo runs

# Polymarket
DEFAULT_PREDICTION_WINDOWS = [1, 3, 7, 14, 30]  # days ahead to predict

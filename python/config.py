"""
Configuration for the Elon Musk tweet tracker and predictor.

No API keys required! Uses Playwright to scrape x.com directly.
Optional: create a .env file for any overrides.
"""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Elon's profile
ELON_USER_ID = "44196397"
ELON_USERNAME = "elonmusk"

# Data collection
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "60"))
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tweets.db")

# HMM Model
N_HIDDEN_STATES = 3  # Low, Medium, High activity states
N_SIMULATIONS = 10_000  # Monte Carlo runs

# Polymarket
DEFAULT_PREDICTION_WINDOWS = [1, 3, 7, 14, 30]  # days ahead to predict

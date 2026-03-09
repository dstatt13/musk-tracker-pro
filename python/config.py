"""
Configuration for the Elon Musk tweet tracker and predictor.

Create a .env file in the python/ directory with:
  X_BEARER_TOKEN=your_bearer_token_here

To get a Bearer Token:
1. Go to https://developer.x.com/en/portal/dashboard
2. Create a project & app (Free tier works for user tweet counts)
3. Generate a Bearer Token under "Keys and Tokens"
"""

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# X API
BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")
ELON_USER_ID = "44196397"  # Elon Musk's X user ID

# Data collection
POLL_INTERVAL_MINUTES = 60  # How often to check tweet count
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tweets.db")

# HMM Model
N_HIDDEN_STATES = 3  # Low, Medium, High activity states
N_SIMULATIONS = 10_000  # Monte Carlo runs

# Polymarket
# Typical Polymarket question: "Will Elon Musk post ≥ X tweets in Y days?"
DEFAULT_PREDICTION_WINDOWS = [1, 3, 7, 14, 30]  # days ahead to predict

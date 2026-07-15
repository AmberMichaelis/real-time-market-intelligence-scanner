"""
Client for interacting with The Odds API.

Responsibilities:
- Build requests to The Odds API.
- Handle API errors.
- Return Python data structures.

This file should NOT:
- Calculate probabilities.
- Match Kalshi markets.
- Store data.
- Execute trades.
"""

import requests

from config import ODDS_API_KEY, require_environment_variable


BASE_URL = "https://api.the-odds-api.com/v4"


def get_nfl_odds() -> list:
    """
    Retrieve upcoming NFL moneyline odds.

    Returns:
        A list of game dictionaries returned by The Odds API.

    Raises:
        RuntimeError:
            If the API request fails.
    """

    api_key = require_environment_variable(
        "ODDS_API_KEY",
        ODDS_API_KEY,
    )

    endpoint = f"{BASE_URL}/sports/americanfootball_nfl/odds"

    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
    }

    try:
        response = requests.get(
            endpoint,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as error:
        raise RuntimeError(
            f"Failed to retrieve NFL odds: {error}"
        ) from error

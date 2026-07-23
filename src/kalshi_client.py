"""
Public market-data client for the Kalshi API.

Responsibilities:
- Retrieve Kalshi markets.
- Retrieve a specific market's order book.
- Handle network, HTTP, and JSON errors.
- Return ordinary Python dictionaries and lists.

This file does NOT:
- Place orders.
- Authenticate a trading account.
- Calculate sportsbook probabilities.
- Match Kalshi markets to sportsbook events.
- Store anything in the database.
"""

from typing import Any

import requests


# The production Kalshi REST API base URL.
BASE_URL = "https://external-api.kalshi.com/trade-api/v2"


class KalshiAPIError(RuntimeError):
    """
    Raised when Kalshi data cannot be retrieved or validated.

    Creating a project-specific exception makes it easier for main.py
    to distinguish a Kalshi failure from other types of errors.
    """


def _get_json(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Send a GET request to Kalshi and return the JSON response.

    The leading underscore in `_get_json` signals that this is an
    internal helper function. Other modules should normally call
    get_markets() or get_market_orderbook() instead.

    Args:
        endpoint:
            API path beginning with a slash, such as "/markets".

        params:
            Optional query parameters sent with the request.

    Returns:
        The decoded JSON response as a dictionary.

    Raises:
        KalshiAPIError:
            If the request times out, the server returns an error,
            the response is not valid JSON, or the JSON has an
            unexpected top-level structure.
    """
    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

        # Convert unsuccessful HTTP responses, such as 404 or 500,
        # into a requests.HTTPError.
        response.raise_for_status()

    except requests.Timeout as error:
        raise KalshiAPIError(
            "The Kalshi API request timed out."
        ) from error

    except requests.HTTPError as error:
        raise KalshiAPIError(
            f"Kalshi returned an HTTP error: {error}"
        ) from error

    except requests.RequestException as error:
        raise KalshiAPIError(
            f"Could not communicate with Kalshi: {error}"
        ) from error

    try:
        data = response.json()

    except requests.JSONDecodeError as error:
        raise KalshiAPIError(
            "Kalshi returned a response that was not valid JSON."
        ) from error

    if not isinstance(data, dict):
        raise KalshiAPIError(
            "Kalshi returned an unexpected JSON structure."
        )

    return data


def get_markets(
    status: str = "open",
    limit: int = 100,
    cursor: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Retrieve one page of Kalshi markets.

    Kalshi paginates large result sets. That means the API may return
    only part of the available data, along with a cursor identifying
    the next page.

    Args:
        status:
            Market status to request. Common values include:
            "open", "closed", "settled", "paused", and "unopened".

        limit:
            Maximum number of markets requested on this page.

        cursor:
            Cursor returned by the previous API response. Leave this
            as None when requesting the first page.

    Returns:
        A tuple containing:

        1. A list of market dictionaries.
        2. The next-page cursor, or None when no cursor is returned.

    Raises:
        ValueError:
            If limit is outside the accepted range.

        KalshiAPIError:
            If the response does not contain a valid markets list.
    """
    if not 1 <= limit <= 1000:
        raise ValueError(
            "The market limit must be between 1 and 1000."
        )

    params: dict[str, Any] = {
        "status": status,
        "limit": limit,
    }

    # We only send cursor when it has an actual value.
    if cursor:
        params["cursor"] = cursor

    data = _get_json(
        endpoint="/markets",
        params=params,
    )

    markets = data.get("markets")

    if not isinstance(markets, list):
        raise KalshiAPIError(
            "Kalshi's response did not contain a valid markets list."
        )

    next_cursor = data.get("cursor")

    if next_cursor is not None and not isinstance(next_cursor, str):
        raise KalshiAPIError(
            "Kalshi returned an invalid pagination cursor."
        )

    return markets, next_cursor


def get_market_orderbook(
    market_ticker: str,
    depth: int | None = None,
) -> dict[str, Any]:
    """
    Retrieve the current order book for one Kalshi market.

    Kalshi returns active YES bids and NO bids. It does not return
    asks directly because an ask on one side can be inferred from
    the best bid on the opposite side.

    Args:
        market_ticker:
            Kalshi's unique identifier for the market.

        depth:
            Optional number of price levels to request.

    Returns:
        The order-book dictionary returned under the API's
        "orderbook" field.

    Raises:
        ValueError:
            If the ticker is blank or depth is invalid.

        KalshiAPIError:
            If Kalshi does not return a valid order book.
    """
    if not market_ticker.strip():
        raise ValueError(
            "A Kalshi market ticker is required."
        )

    params: dict[str, Any] = {}

    if depth is not None:
        if depth < 1:
            raise ValueError(
                "Order-book depth must be at least 1."
            )

        params["depth"] = depth

    data = _get_json(
        endpoint=f"/markets/{market_ticker}/orderbook",
        params=params or None,
    )

    orderbook = data.get("orderbook")

    if not isinstance(orderbook, dict):
        raise KalshiAPIError(
            "Kalshi's response did not contain a valid order book."
        )

    return orderbook

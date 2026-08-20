"""
Unit tests for the Kalshi public market-data client.

These tests verify:
- Successful market retrieval.
- Pagination behavior.
- Repeated-cursor protection.
- Order-book retrieval.
- HTTP and network error handling.
- Invalid JSON handling.
- Invalid response-shape handling.

No real HTTP requests are made.
"""

from unittest.mock import Mock

import pytest
import requests

import kalshi_client


@pytest.fixture
def sample_markets() -> list[dict]:
    """
    Return representative Kalshi market data.
    """
    return [
        {
            "ticker": "KXNFLGAME-TEST-SEA",
            "event_ticker": "KXNFLGAME-TEST",
            "series_ticker": "KXNFLGAME",
            "title": (
                "Seattle Seahawks vs New England Patriots"
            ),
            "subtitle": "Professional football game",
            "status": "open",
            "yes_bid": 57,
            "yes_ask": 58,
            "no_bid": 42,
            "no_ask": 43,
        },
        {
            "ticker": "KXNFLGAME-TEST-KC",
            "event_ticker": "KXNFLGAME-TEST-2",
            "series_ticker": "KXNFLGAME",
            "title": (
                "Kansas City Chiefs vs Buffalo Bills"
            ),
            "subtitle": "Professional football game",
            "status": "open",
            "yes_bid": 61,
            "yes_ask": 62,
            "no_bid": 38,
            "no_ask": 39,
        },
    ]


def build_mock_response(
    json_data,
) -> Mock:
    """
    Build a normal successful requests.Response-like mock.
    """
    response = Mock()

    response.json.return_value = json_data
    response.raise_for_status.return_value = None

    return response


# ---------------------------------------------------------------------
# Low-level JSON retrieval
# ---------------------------------------------------------------------


def test_get_json_returns_dictionary(
    monkeypatch,
) -> None:
    """
    _get_json should return a decoded JSON dictionary.
    """
    response = build_mock_response(
        {
            "hello": "world",
        }
    )

    mock_get = Mock(
        return_value=response
    )

    monkeypatch.setattr(
        kalshi_client.requests,
        "get",
        mock_get,
    )

    result = kalshi_client._get_json(
        "/markets"
    )

    assert result == {
        "hello": "world",
    }


def test_get_json_builds_correct_url(
    monkeypatch,
) -> None:
    """
    The endpoint should be appended to the configured BASE_URL.
    """
    response = build_mock_response(
        {
            "markets": [],
        }
    )

    mock_get = Mock(
        return_value=response
    )

    monkeypatch.setattr(
        kalshi_client.requests,
        "get",
        mock_get,
    )

    kalshi_client._get_json(
        "/markets"
    )

    requested_url = mock_get.call_args.args[0]

    assert requested_url == (
        f"{kalshi_client.BASE_URL}/markets"
    )


def test_get_json_passes_query_parameters(
    monkeypatch,
) -> None:
    response = build_mock_response(
        {
            "markets": [],
        }
    )

    mock_get = Mock(
        return_value=response
    )

    monkeypatch.setattr(
        kalshi_client.requests,
        "get",
        mock_get,
    )

    params = {
        "status": "open",
        "limit": 100,
    }

    kalshi_client._get_json(
        "/markets",
        params=params,
    )

    assert mock_get.call_args.kwargs[
        "params"
    ] == params


def test_get_json_uses_timeout(
    monkeypatch,
) -> None:
    """
    Kalshi requests should not be allowed to hang indefinitely.
    """
    response = build_mock_response(
        {
            "markets": [],
        }
    )

    mock_get = Mock(
        return_value=response
    )

    monkeypatch.setattr(
        kalshi_client.requests,
        "get",
        mock_get,
    )

    kalshi_client._get_json(
        "/markets"
    )

    assert mock_get.call_args.kwargs[
        "timeout"
    ] == 10


def test_get_json_calls_raise_for_status(
    monkeypatch,
) -> None:
    response = build_mock_response(
        {
            "markets": [],
        }
    )

    monkeypatch.setattr(
        kalshi_client.requests,
        "get",
        Mock(return_value=response),
    )

    kalshi_client._get_json(
        "/markets"
    )

    response.raise_for_status.assert_called_once()


def test_timeout_becomes_kalshi_api_error(
    monkeypatch,
) -> None:
    """
    A timeout should become a project-specific KalshiAPIError.
    """
    monkeypatch.setattr(
        kalshi_client.requests,
        "get",
        Mock(
            side_effect=requests.Timeout(
                "Timed out"
            )
        ),
    )

    with pytest.raises(
        kalshi_client.KalshiAPIError,
        match="timed out",
    ):
        kalshi_client._get_json(
            "/markets"
        )


def test_http_error_becomes_kalshi_api_error(
    monkeypatch,
) -> None:
    """
    An HTTP error such as 503 should be wrapped cleanly.
    """
    response = Mock()

    response.raise_for_status.side_effect = (
        requests.HTTPError(
            "503 Service Unavailable"
        )
    )

    monkeypatch.setattr(
        kalshi_client.requests,
        "get",
        Mock(return_value=response),
    )

    with pytest.raises(
        kalshi_client.KalshiAPIError,
        match="HTTP error",
    ):
        kalshi_client._get_json(
            "/markets"
        )


def test_connection_error_becomes_kalshi_api_error(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        kalshi_client.requests,
        "get",
        Mock(
            side_effect=requests.ConnectionError(
                "Connection failed"
            )
        ),
    )

    with pytest.raises(
        kalshi_client.KalshiAPIError,
        match="Could not communicate",
    ):
        kalshi_client._get_json(
            "/markets"
        )


def test_invalid_json_becomes_kalshi_api_error(
    monkeypatch,
) -> None:
    response = Mock()

    response.raise_for_status.return_value = None

    response.json.side_effect = (
        requests.JSONDecodeError(
            "Invalid JSON",
            "not-json",
            0,
        )
    )

    monkeypatch.setattr(
        kalshi_client.requests,
        "get",
        Mock(return_value=response),
    )

    with pytest.raises(
        kalshi_client.KalshiAPIError,
        match="not valid JSON",
    ):
        kalshi_client._get_json(
            "/markets"
        )


def test_non_dictionary_json_is_rejected(
    monkeypatch,
) -> None:
    response = build_mock_response(
        [
            {
                "unexpected": "list",
            }
        ]
    )

    monkeypatch.setattr(
        kalshi_client.requests,
        "get",
        Mock(return_value=response),
    )

    with pytest.raises(
        kalshi_client.KalshiAPIError,
        match="unexpected JSON structure",
    ):
        kalshi_client._get_json(
            "/markets"
        )


# ---------------------------------------------------------------------
# get_markets()
# ---------------------------------------------------------------------


def test_get_markets_returns_market_list(
    monkeypatch,
    sample_markets,
) -> None:
    """
    get_markets should unpack the markets array and cursor.
    """
    mock_get_json = Mock(
        return_value={
            "markets": sample_markets,
            "cursor": "next-page",
        }
    )

    monkeypatch.setattr(
        kalshi_client,
        "_get_json",
        mock_get_json,
    )

    markets, cursor = (
        kalshi_client.get_markets(
            status="open",
            limit=100,
        )
    )

    assert markets == sample_markets
    assert cursor == "next-page"


def test_get_markets_passes_status_and_limit(
    monkeypatch,
) -> None:
    mock_get_json = Mock(
        return_value={
            "markets": [],
            "cursor": None,
        }
    )

    monkeypatch.setattr(
        kalshi_client,
        "_get_json",
        mock_get_json,
    )

    kalshi_client.get_markets(
        status="open",
        limit=250,
    )

    params = mock_get_json.call_args.kwargs[
        "params"
    ]

    assert params["status"] == "open"
    assert params["limit"] == 250


def test_get_markets_includes_cursor_when_present(
    monkeypatch,
) -> None:
    mock_get_json = Mock(
        return_value={
            "markets": [],
            "cursor": None,
        }
    )

    monkeypatch.setattr(
        kalshi_client,
        "_get_json",
        mock_get_json,
    )

    kalshi_client.get_markets(
        cursor="abc123"
    )

    params = mock_get_json.call_args.kwargs[
        "params"
    ]

    assert params["cursor"] == "abc123"


def test_get_markets_does_not_send_blank_cursor(
    monkeypatch,
) -> None:
    mock_get_json = Mock(
        return_value={
            "markets": [],
            "cursor": None,
        }
    )

    monkeypatch.setattr(
        kalshi_client,
        "_get_json",
        mock_get_json,
    )

    kalshi_client.get_markets(
        cursor=None
    )

    params = mock_get_json.call_args.kwargs[
        "params"
    ]

    assert "cursor" not in params


def test_get_markets_rejects_limit_below_one() -> None:
    with pytest.raises(ValueError):
        kalshi_client.get_markets(
            limit=0
        )


def test_get_markets_rejects_limit_above_1000() -> None:
    with pytest.raises(ValueError):
        kalshi_client.get_markets(
            limit=1001
        )


def test_get_markets_rejects_missing_markets_list(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        kalshi_client,
        "_get_json",
        Mock(
            return_value={
                "cursor": None,
            }
        ),
    )

    with pytest.raises(
        kalshi_client.KalshiAPIError,
        match="markets list",
    ):
        kalshi_client.get_markets()


def test_get_markets_rejects_invalid_cursor_type(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        kalshi_client,
        "_get_json",
        Mock(
            return_value={
                "markets": [],
                "cursor": 12345,
            }
        ),
    )

    with pytest.raises(
        kalshi_client.KalshiAPIError,
        match="pagination cursor",
    ):
        kalshi_client.get_markets()


# ---------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------


def test_get_all_markets_combines_pages(
    monkeypatch,
) -> None:
    """
    Multiple Kalshi pages should be combined into one list.
    """
    first_page = [
        {
            "ticker": "MARKET-A",
        }
    ]

    second_page = [
        {
            "ticker": "MARKET-B",
        }
    ]

    mock_get_markets = Mock(
        side_effect=[
            (
                first_page,
                "cursor-2",
            ),
            (
                second_page,
                None,
            ),
        ]
    )

    monkeypatch.setattr(
        kalshi_client,
        "get_markets",
        mock_get_markets,
    )

    result = kalshi_client.get_all_markets(
        page_limit=1000,
        max_pages=10,
    )

    assert result == (
        first_page
        + second_page
    )

    assert mock_get_markets.call_count == 2


def test_get_all_markets_passes_cursor_to_next_page(
    monkeypatch,
) -> None:
    mock_get_markets = Mock(
        side_effect=[
            (
                [],
                "cursor-2",
            ),
            (
                [],
                None,
            ),
        ]
    )

    monkeypatch.setattr(
        kalshi_client,
        "get_markets",
        mock_get_markets,
    )

    kalshi_client.get_all_markets(
        max_pages=10
    )

    first_call = (
        mock_get_markets.call_args_list[0]
    )

    second_call = (
        mock_get_markets.call_args_list[1]
    )

    assert first_call.kwargs[
        "cursor"
    ] is None

    assert second_call.kwargs[
        "cursor"
    ] == "cursor-2"


def test_get_all_markets_stops_when_cursor_missing(
    monkeypatch,
) -> None:
    mock_get_markets = Mock(
        return_value=(
            [
                {
                    "ticker": "ONLY-MARKET",
                }
            ],
            None,
        )
    )

    monkeypatch.setattr(
        kalshi_client,
        "get_markets",
        mock_get_markets,
    )

    kalshi_client.get_all_markets(
        max_pages=10
    )

    assert mock_get_markets.call_count == 1


def test_get_all_markets_rejects_repeated_cursor(
    monkeypatch,
) -> None:
    """
    Repeated cursors could create an infinite pagination loop.
    """
    mock_get_markets = Mock(
        side_effect=[
            (
                [],
                "same-cursor",
            ),
            (
                [],
                "same-cursor",
            ),
        ]
    )

    monkeypatch.setattr(
        kalshi_client,
        "get_markets",
        mock_get_markets,
    )

    with pytest.raises(
        kalshi_client.KalshiAPIError,
        match="repeated pagination cursor",
    ):
        kalshi_client.get_all_markets(
            max_pages=10
        )


def test_get_all_markets_respects_max_pages(
    monkeypatch,
) -> None:
    """
    A safety limit should prevent endless API traversal.
    """
    mock_get_markets = Mock(
        side_effect=[
            (
                [
                    {
                        "ticker": "A",
                    }
                ],
                "cursor-2",
            ),
            (
                [
                    {
                        "ticker": "B",
                    }
                ],
                "cursor-3",
            ),
        ]
    )

    monkeypatch.setattr(
        kalshi_client,
        "get_markets",
        mock_get_markets,
    )

    result = kalshi_client.get_all_markets(
        max_pages=2
    )

    assert len(result) == 2
    assert mock_get_markets.call_count == 2


def test_get_all_markets_rejects_invalid_page_limit() -> None:
    with pytest.raises(ValueError):
        kalshi_client.get_all_markets(
            page_limit=0
        )


def test_get_all_markets_rejects_invalid_max_pages() -> None:
    with pytest.raises(ValueError):
        kalshi_client.get_all_markets(
            max_pages=0
        )


# ---------------------------------------------------------------------
# Order-book retrieval
# ---------------------------------------------------------------------


def test_get_market_orderbook_returns_orderbook(
    monkeypatch,
) -> None:
    orderbook = {
        "yes": [
            [
                57,
                25,
            ]
        ],
        "no": [
            [
                42,
                18,
            ]
        ],
    }

    mock_get_json = Mock(
        return_value={
            "orderbook": orderbook,
        }
    )

    monkeypatch.setattr(
        kalshi_client,
        "_get_json",
        mock_get_json,
    )

    result = (
        kalshi_client.get_market_orderbook(
            "KXNFLGAME-TEST-SEA"
        )
    )

    assert result == orderbook


def test_get_market_orderbook_uses_correct_endpoint(
    monkeypatch,
) -> None:
    mock_get_json = Mock(
        return_value={
            "orderbook": {},
        }
    )

    monkeypatch.setattr(
        kalshi_client,
        "_get_json",
        mock_get_json,
    )

    kalshi_client.get_market_orderbook(
        "KXNFLGAME-TEST-SEA"
    )

    endpoint = mock_get_json.call_args.kwargs[
        "endpoint"
    ]

    assert endpoint == (
        "/markets/"
        "KXNFLGAME-TEST-SEA/"
        "orderbook"
    )


def test_get_market_orderbook_passes_depth(
    monkeypatch,
) -> None:
    mock_get_json = Mock(
        return_value={
            "orderbook": {},
        }
    )

    monkeypatch.setattr(
        kalshi_client,
        "_get_json",
        mock_get_json,
    )

    kalshi_client.get_market_orderbook(
        "KXNFLGAME-TEST-SEA",
        depth=5,
    )

    params = mock_get_json.call_args.kwargs[
        "params"
    ]

    assert params["depth"] == 5


def test_get_market_orderbook_blank_ticker_fails() -> None:
    with pytest.raises(ValueError):
        kalshi_client.get_market_orderbook(
            "   "
        )


def test_get_market_orderbook_invalid_depth_fails() -> None:
    with pytest.raises(ValueError):
        kalshi_client.get_market_orderbook(
            "KXNFLGAME-TEST-SEA",
            depth=0,
        )


def test_get_market_orderbook_missing_orderbook_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        kalshi_client,
        "_get_json",
        Mock(
            return_value={
                "something_else": {},
            }
        ),
    )

    with pytest.raises(
        kalshi_client.KalshiAPIError,
        match="valid order book",
    ):
        kalshi_client.get_market_orderbook(
            "KXNFLGAME-TEST-SEA"
        )

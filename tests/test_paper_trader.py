"""
Unit tests for paper-trading and opportunity analysis.

These tests verify:
- Kalshi price parsing.
- Edge calculations.
- Return-on-cost calculations.
- Consensus lookup.
- Opportunity creation.
- Minimum edge filtering.
- Confidence filtering.
- Rejection of invalid or non-executable prices.
"""

from datetime import datetime, timezone

import pytest

from matcher import MarketMatch
from paper_trader import (
    build_yes_opportunity,
    calculate_edge_cents,
    calculate_return_on_cost,
    find_trade_opportunities,
    get_consensus_probability_for_team,
    parse_price_cents,
)


def build_test_game() -> dict:
    """
    Return a sportsbook game with two bookmakers.

    The exact odds are chosen so the Seattle Seahawks are the favorite.
    """
    return {
        "id": "game-123",
        "sport_key": "americanfootball_nfl",
        "sport_title": "NFL",
        "home_team": "Seattle Seahawks",
        "away_team": "New England Patriots",
        "commence_time": "2026-09-10T00:15:00Z",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {
                                "name": "New England Patriots",
                                "price": 160,
                            },
                            {
                                "name": "Seattle Seahawks",
                                "price": -192,
                            },
                        ],
                    }
                ],
            },
            {
                "key": "fanduel",
                "title": "FanDuel",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {
                                "name": "New England Patriots",
                                "price": 166,
                            },
                            {
                                "name": "Seattle Seahawks",
                                "price": -198,
                            },
                        ],
                    }
                ],
            },
        ],
    }


def build_test_market(
    yes_ask: float = 58,
) -> dict:
    """
    Return a representative Kalshi market.
    """
    return {
        "ticker": "KXNFLGAME-TEST-SEA",
        "title": (
            "Seattle Seahawks vs New England Patriots"
        ),
        "yes_sub_title": "Seattle Seahawks",
        "no_sub_title": "New England Patriots",
        "yes_bid": 57,
        "yes_ask": yes_ask,
        "status": "open",
    }


def build_test_match(
    yes_ask: float = 58,
    confidence_score: int = 100,
) -> MarketMatch:
    """
    Return a verified sportsbook-to-Kalshi match.
    """
    return MarketMatch(
        sportsbook_game=build_test_game(),
        kalshi_market=build_test_market(
            yes_ask=yes_ask,
        ),
        yes_team="Seattle Seahawks",
        no_team="New England Patriots",
        time_difference_hours=0.25,
        confidence_score=confidence_score,
        reasons=[
            "Both teams matched.",
            "YES side identified.",
        ],
    )


def test_parse_integer_price() -> None:
    assert parse_price_cents(
        58
    ) == pytest.approx(58)


def test_parse_float_price() -> None:
    assert parse_price_cents(
        58.5
    ) == pytest.approx(58.5)


def test_parse_string_price() -> None:
    assert parse_price_cents(
        "58.25"
    ) == pytest.approx(58.25)


def test_parse_price_with_whitespace() -> None:
    assert parse_price_cents(
        " 58 "
    ) == pytest.approx(58)


def test_parse_invalid_string_returns_none() -> None:
    assert parse_price_cents(
        "not-a-price"
    ) is None


def test_parse_none_returns_none() -> None:
    assert parse_price_cents(
        None
    ) is None


def test_parse_boolean_returns_none() -> None:
    """
    bool is technically a subclass of int in Python, so the explicit
    boolean check in parse_price_cents() matters.
    """
    assert parse_price_cents(
        True
    ) is None


def test_parse_negative_price_returns_none() -> None:
    assert parse_price_cents(
        -1
    ) is None


def test_parse_price_above_100_returns_none() -> None:
    assert parse_price_cents(
        101
    ) is None


def test_calculate_positive_edge() -> None:
    edge = calculate_edge_cents(
        fair_value_cents=63,
        market_price_cents=58,
    )

    assert edge == pytest.approx(
        5
    )


def test_calculate_zero_edge() -> None:
    edge = calculate_edge_cents(
        fair_value_cents=63,
        market_price_cents=63,
    )

    assert edge == pytest.approx(
        0
    )


def test_calculate_negative_edge() -> None:
    """
    A negative edge means the market appears overpriced.
    """
    edge = calculate_edge_cents(
        fair_value_cents=60,
        market_price_cents=65,
    )

    assert edge == pytest.approx(
        -5
    )


def test_invalid_fair_value_raises_error() -> None:
    with pytest.raises(ValueError):
        calculate_edge_cents(
            fair_value_cents=110,
            market_price_cents=50,
        )


def test_invalid_market_price_raises_error() -> None:
    with pytest.raises(ValueError):
        calculate_edge_cents(
            fair_value_cents=50,
            market_price_cents=-10,
        )


def test_return_on_cost() -> None:
    """
    Five cents of estimated edge on a 58-cent contract is about 8.62%.
    """
    result = calculate_return_on_cost(
        edge_cents=5,
        market_price_cents=58,
    )

    assert result == pytest.approx(
        5 / 58
    )


def test_negative_return_on_cost_allowed() -> None:
    """
    An overpriced contract can produce a negative pricing edge.
    """
    result = calculate_return_on_cost(
        edge_cents=-5,
        market_price_cents=65,
    )

    assert result == pytest.approx(
        -5 / 65
    )


def test_zero_market_price_raises_error() -> None:
    with pytest.raises(ValueError):
        calculate_return_on_cost(
            edge_cents=5,
            market_price_cents=0,
        )


def test_consensus_probability_for_team() -> None:
    probability = get_consensus_probability_for_team(
        sportsbook_game=build_test_game(),
        team="Seattle Seahawks",
    )

    assert probability is not None
    assert 0 < probability < 1


def test_missing_team_consensus_returns_none() -> None:
    probability = get_consensus_probability_for_team(
        sportsbook_game=build_test_game(),
        team="Imaginary Football Team",
    )

    assert probability is None


def test_build_yes_opportunity() -> None:
    match = build_test_match(
        yes_ask=58
    )

    opportunity = build_yes_opportunity(
        match
    )

    assert opportunity is not None

    assert opportunity.team == (
        "Seattle Seahawks"
    )

    assert opportunity.contract_side == "yes"

    assert opportunity.kalshi_ticker == (
        "KXNFLGAME-TEST-SEA"
    )

    assert opportunity.market_price_cents == pytest.approx(
        58
    )

    assert opportunity.fair_probability > 0
    assert opportunity.fair_probability < 1

    assert opportunity.fair_value_cents == pytest.approx(
        opportunity.fair_probability * 100
    )

    assert opportunity.edge_cents == pytest.approx(
        opportunity.fair_value_cents
        - opportunity.market_price_cents
    )

    assert opportunity.observed_at.tzinfo is not None


def test_opportunity_preserves_confidence_score() -> None:
    match = build_test_match(
        confidence_score=92
    )

    opportunity = build_yes_opportunity(
        match
    )

    assert opportunity is not None
    assert opportunity.confidence_score == 92


def test_zero_ask_is_not_executable() -> None:
    """
    A zero ask is treated as unavailable rather than as a free contract.
    """
    match = build_test_match(
        yes_ask=0
    )

    opportunity = build_yes_opportunity(
        match
    )

    assert opportunity is None


def test_invalid_ask_is_rejected() -> None:
    match = build_test_match()

    match.kalshi_market["yes_ask"] = (
        "not-a-number"
    )

    opportunity = build_yes_opportunity(
        match
    )

    assert opportunity is None


def test_missing_game_id_is_rejected() -> None:
    match = build_test_match()

    match.sportsbook_game["id"] = ""

    opportunity = build_yes_opportunity(
        match
    )

    assert opportunity is None


def test_missing_kalshi_ticker_is_rejected() -> None:
    match = build_test_match()

    match.kalshi_market["ticker"] = ""

    opportunity = build_yes_opportunity(
        match
    )

    assert opportunity is None


def test_find_trade_opportunities_returns_good_edge() -> None:
    """
    A sufficiently cheap contract should pass the minimum-edge filter.
    """
    match = build_test_match(
        yes_ask=50
    )

    opportunities = find_trade_opportunities(
        matches=[
            match,
        ],
        minimum_edge_cents=3,
        minimum_confidence_score=80,
    )

    assert len(opportunities) == 1


def test_find_trade_opportunities_rejects_small_edge() -> None:
    """
    An expensive contract should not pass a 3-cent minimum edge.
    """
    match = build_test_match(
        yes_ask=63
    )

    opportunities = find_trade_opportunities(
        matches=[
            match,
        ],
        minimum_edge_cents=3,
        minimum_confidence_score=80,
    )

    assert opportunities == []


def test_low_confidence_match_is_rejected() -> None:
    match = build_test_match(
        yes_ask=50,
        confidence_score=70,
    )

    opportunities = find_trade_opportunities(
        matches=[
            match,
        ],
        minimum_edge_cents=3,
        minimum_confidence_score=80,
    )

    assert opportunities == []


def test_opportunities_sorted_by_largest_edge() -> None:
    cheaper_market = build_test_match(
        yes_ask=45
    )

    more_expensive_market = build_test_match(
        yes_ask=50
    )

    # Give the second market a unique ticker.
    more_expensive_market.kalshi_market[
        "ticker"
    ] = "KXNFLGAME-TEST-SEA-2"

    opportunities = find_trade_opportunities(
        matches=[
            more_expensive_market,
            cheaper_market,
        ],
        minimum_edge_cents=0,
    )

    assert len(opportunities) == 2

    assert (
        opportunities[0].edge_cents
        >= opportunities[1].edge_cents
    )


def test_negative_minimum_edge_raises_error() -> None:
    with pytest.raises(ValueError):
        find_trade_opportunities(
            matches=[],
            minimum_edge_cents=-1,
        )


def test_invalid_minimum_confidence_raises_error() -> None:
    with pytest.raises(ValueError):
        find_trade_opportunities(
            matches=[],
            minimum_confidence_score=101,
        )

"""
Tests for the reporting layer.

These tests verify:
- Table counts.
- Latest sportsbook scan summaries.
- Latest Kalshi scan summaries.
- Retrieval of recent verified matches.
- Retrieval of top paper-trade opportunities.
- Human-readable report generation.

All tests use temporary SQLite databases.
"""

from datetime import datetime, timezone

import pytest

from database import (
    initialize_database,
    save_kalshi_markets,
    save_sportsbook_games,
    save_trade_opportunities,
    save_verified_matches,
)
from matcher import MarketMatch
from paper_trader import TradeOpportunity
from reporting import (
    build_text_report,
    get_latest_kalshi_observation,
    get_latest_sportsbook_observation,
    get_recent_verified_matches,
    get_table_counts,
    get_top_opportunities,
)


@pytest.fixture
def database_path(tmp_path):
    """
    Create a fresh temporary database for each test.
    """
    path = tmp_path / "reporting_test.db"

    initialize_database(path)

    return path


def build_test_game(
    game_id: str = "game-123",
) -> dict:
    """
    Return a representative sportsbook game.
    """
    return {
        "id": game_id,
        "sport_key": "americanfootball_nfl",
        "sport_title": "NFL",
        "home_team": "Seattle Seahawks",
        "away_team": "New England Patriots",
        "commence_time": "2026-09-10T00:15:00Z",
    }


def build_test_market(
    ticker: str = "KXNFLGAME-TEST-SEA",
) -> dict:
    """
    Return a representative Kalshi market.
    """
    return {
        "ticker": ticker,
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
        "close_time": "2026-09-10T00:30:00Z",
    }


def build_test_match() -> MarketMatch:
    """
    Return a representative verified match.
    """
    return MarketMatch(
        sportsbook_game=build_test_game(),
        kalshi_market=build_test_market(),
        yes_team="Seattle Seahawks",
        no_team="New England Patriots",
        time_difference_hours=0.25,
        confidence_score=100,
        reasons=[
            "Both teams matched.",
            "YES side identified.",
        ],
    )


def build_test_opportunity(
    ticker: str = "KXNFLGAME-TEST-SEA",
    edge_cents: float = 5.0,
) -> TradeOpportunity:
    """
    Return a representative paper-trade opportunity.
    """
    fair_value = 63.0

    market_price = (
        fair_value - edge_cents
    )

    return TradeOpportunity(
        sportsbook_game_id="game-123",
        kalshi_ticker=ticker,
        team="Seattle Seahawks",
        contract_side="yes",
        fair_probability=0.63,
        fair_value_cents=fair_value,
        market_price_cents=market_price,
        edge_cents=edge_cents,
        edge_percentage_points=edge_cents,
        estimated_return_on_cost=(
            edge_cents / market_price
        ),
        confidence_score=100,
        observed_at=datetime(
            2026,
            9,
            1,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )


# ---------------------------------------------------------------------
# Table counts
# ---------------------------------------------------------------------


def test_empty_table_counts(
    database_path,
) -> None:
    """
    A new database should contain zero records.
    """
    counts = get_table_counts(
        database_path
    )

    assert counts == {
        "sportsbook_games": 0,
        "kalshi_market_snapshots": 0,
        "verified_matches": 0,
        "paper_trade_opportunities": 0,
    }


def test_table_counts_after_inserts(
    database_path,
) -> None:
    """
    Reporting counts should reflect stored records.
    """
    save_sportsbook_games(
        [build_test_game()],
        database_path=database_path,
    )

    save_kalshi_markets(
        [build_test_market()],
        database_path=database_path,
    )

    save_verified_matches(
        [build_test_match()],
        database_path=database_path,
    )

    save_trade_opportunities(
        [build_test_opportunity()],
        database_path=database_path,
    )

    counts = get_table_counts(
        database_path
    )

    assert counts == {
        "sportsbook_games": 1,
        "kalshi_market_snapshots": 1,
        "verified_matches": 1,
        "paper_trade_opportunities": 1,
    }


# ---------------------------------------------------------------------
# Latest sportsbook observation
# ---------------------------------------------------------------------


def test_latest_sportsbook_observation_empty(
    database_path,
) -> None:
    result = get_latest_sportsbook_observation(
        database_path
    )

    assert result is None


def test_latest_sportsbook_observation(
    database_path,
) -> None:
    first_time = datetime(
        2026,
        9,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    second_time = datetime(
        2026,
        9,
        1,
        12,
        5,
        tzinfo=timezone.utc,
    )

    save_sportsbook_games(
        [
            build_test_game(
                "game-1"
            ),
        ],
        observed_at=first_time,
        database_path=database_path,
    )

    save_sportsbook_games(
        [
            build_test_game(
                "game-2"
            ),
            build_test_game(
                "game-3"
            ),
        ],
        observed_at=second_time,
        database_path=database_path,
    )

    result = get_latest_sportsbook_observation(
        database_path
    )

    assert result is not None

    assert result[
        "observed_at"
    ] == second_time.isoformat()

    assert result[
        "game_count"
    ] == 2


# ---------------------------------------------------------------------
# Latest Kalshi observation
# ---------------------------------------------------------------------


def test_latest_kalshi_observation_empty(
    database_path,
) -> None:
    result = get_latest_kalshi_observation(
        database_path
    )

    assert result is None


def test_latest_kalshi_observation(
    database_path,
) -> None:
    first_time = datetime(
        2026,
        9,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    second_time = datetime(
        2026,
        9,
        1,
        12,
        10,
        tzinfo=timezone.utc,
    )

    save_kalshi_markets(
        [
            build_test_market(
                "MARKET-1"
            ),
        ],
        observed_at=first_time,
        database_path=database_path,
    )

    save_kalshi_markets(
        [
            build_test_market(
                "MARKET-2"
            ),
            build_test_market(
                "MARKET-3"
            ),
        ],
        observed_at=second_time,
        database_path=database_path,
    )

    result = get_latest_kalshi_observation(
        database_path
    )

    assert result is not None

    assert result[
        "observed_at"
    ] == second_time.isoformat()

    assert result[
        "market_count"
    ] == 2


# ---------------------------------------------------------------------
# Top opportunities
# ---------------------------------------------------------------------


def test_top_opportunities_empty(
    database_path,
) -> None:
    results = get_top_opportunities(
        database_path=database_path,
    )

    assert results == []


def test_top_opportunities_sorted_by_edge(
    database_path,
) -> None:
    low_edge = build_test_opportunity(
        ticker="LOW-EDGE",
        edge_cents=2,
    )

    high_edge = build_test_opportunity(
        ticker="HIGH-EDGE",
        edge_cents=8,
    )

    medium_edge = build_test_opportunity(
        ticker="MEDIUM-EDGE",
        edge_cents=5,
    )

    save_trade_opportunities(
        [
            low_edge,
            high_edge,
            medium_edge,
        ],
        database_path=database_path,
    )

    results = get_top_opportunities(
        limit=3,
        database_path=database_path,
    )

    assert len(results) == 3

    assert results[0][
        "kalshi_ticker"
    ] == "HIGH-EDGE"

    assert results[1][
        "kalshi_ticker"
    ] == "MEDIUM-EDGE"

    assert results[2][
        "kalshi_ticker"
    ] == "LOW-EDGE"


def test_top_opportunities_respects_limit(
    database_path,
) -> None:
    save_trade_opportunities(
        [
            build_test_opportunity(
                ticker="A",
                edge_cents=2,
            ),
            build_test_opportunity(
                ticker="B",
                edge_cents=4,
            ),
            build_test_opportunity(
                ticker="C",
                edge_cents=6,
            ),
        ],
        database_path=database_path,
    )

    results = get_top_opportunities(
        limit=2,
        database_path=database_path,
    )

    assert len(results) == 2


def test_invalid_opportunity_limit_fails(
    database_path,
) -> None:
    with pytest.raises(ValueError):
        get_top_opportunities(
            limit=0,
            database_path=database_path,
        )


# ---------------------------------------------------------------------
# Recent verified matches
# ---------------------------------------------------------------------


def test_recent_verified_matches_empty(
    database_path,
) -> None:
    results = get_recent_verified_matches(
        database_path=database_path,
    )

    assert results == []


def test_recent_verified_matches_returns_match(
    database_path,
) -> None:
    save_verified_matches(
        [
            build_test_match(),
        ],
        database_path=database_path,
    )

    results = get_recent_verified_matches(
        database_path=database_path,
    )

    assert len(results) == 1

    assert results[0][
        "yes_team"
    ] == "Seattle Seahawks"

    assert results[0][
        "no_team"
    ] == "New England Patriots"

    assert results[0][
        "confidence_score"
    ] == 100


def test_invalid_match_limit_fails(
    database_path,
) -> None:
    with pytest.raises(ValueError):
        get_recent_verified_matches(
            limit=0,
            database_path=database_path,
        )


# ---------------------------------------------------------------------
# Full text report
# ---------------------------------------------------------------------


def test_empty_report_contains_project_title(
    database_path,
) -> None:
    report = build_text_report(
        database_path
    )

    assert (
        "REAL-TIME MARKET INTELLIGENCE SCANNER"
        in report
    )


def test_empty_report_contains_zero_counts(
    database_path,
) -> None:
    report = build_text_report(
        database_path
    )

    assert (
        "Sportsbook snapshots: 0"
        in report
    )

    assert (
        "Kalshi market snapshots: 0"
        in report
    )

    assert (
        "Verified matches: 0"
        in report
    )

    assert (
        "Paper-trade opportunities: 0"
        in report
    )


def test_empty_report_explains_missing_matches(
    database_path,
) -> None:
    report = build_text_report(
        database_path
    )

    assert (
        "No verified sportsbook-to-Kalshi matches"
        in report
    )


def test_empty_report_explains_missing_opportunities(
    database_path,
) -> None:
    report = build_text_report(
        database_path
    )

    assert (
        "No paper-trade opportunities"
        in report
    )


def test_report_contains_latest_scan_information(
    database_path,
) -> None:
    observed_at = datetime(
        2026,
        9,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    save_sportsbook_games(
        [
            build_test_game(),
        ],
        observed_at=observed_at,
        database_path=database_path,
    )

    save_kalshi_markets(
        [
            build_test_market(),
        ],
        observed_at=observed_at,
        database_path=database_path,
    )

    report = build_text_report(
        database_path
    )

    assert "Sportsbook games: 1" in report
    assert "Kalshi markets: 1" in report

    assert observed_at.isoformat() in report


def test_report_contains_verified_match(
    database_path,
) -> None:
    save_verified_matches(
        [
            build_test_match(),
        ],
        database_path=database_path,
    )

    report = build_text_report(
        database_path
    )

    assert (
        "Seattle Seahawks vs New England Patriots"
        in report
    )

    assert (
        "KXNFLGAME-TEST-SEA"
        in report
    )

    assert (
        "Confidence: 100/100"
        in report
    )


def test_report_contains_trade_opportunity(
    database_path,
) -> None:
    save_trade_opportunities(
        [
            build_test_opportunity(),
        ],
        database_path=database_path,
    )

    report = build_text_report(
        database_path
    )

    assert "Seattle Seahawks (YES)" in report

    assert "Fair probability: 63.00%" in report

    assert "Fair value: 63.00¢" in report

    assert "Market price: 58.00¢" in report

    assert "Edge: 5.00¢" in report


def test_report_includes_all_sections(
    database_path,
) -> None:
    report = build_text_report(
        database_path
    )

    assert "DATABASE TOTALS" in report
    assert "LATEST SCAN" in report
    assert "RECENT VERIFIED MATCHES" in report
    assert "TOP PAPER-TRADE OPPORTUNITIES" in report

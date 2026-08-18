"""
Integration tests for the SQLite persistence layer.

These tests verify:
- Database initialization.
- Table creation.
- Connection configuration.
- Sportsbook snapshot persistence.
- Kalshi snapshot persistence.
- Verified-match persistence.
- Paper-trade opportunity persistence.
- Duplicate protection.
- Invalid-record handling.
- Database statistics.

All tests use temporary databases. The real project database is never
modified.
"""

from datetime import datetime, timezone
import json
import sqlite3

import pytest

from database import (
    get_connection,
    get_database_statistics,
    initialize_database,
    save_kalshi_markets,
    save_sportsbook_games,
    save_trade_opportunities,
    save_verified_matches,
)
from matcher import MarketMatch
from paper_trader import TradeOpportunity


@pytest.fixture
def database_path(tmp_path):
    """
    Create and initialize a fresh temporary database for each test.

    pytest automatically deletes tmp_path after the test session.
    """
    path = tmp_path / "test_scanner.db"

    initialize_database(path)

    return path


def build_test_game() -> dict:
    """Return a representative sportsbook game."""
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
            }
        ],
    }


def build_test_market() -> dict:
    """Return a representative Kalshi market."""
    return {
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
        "volume": 1250,
        "liquidity": 5000,
        "close_time": "2026-09-10T00:30:00Z",
    }


def build_test_match() -> MarketMatch:
    """Return a representative verified market match."""
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


def build_test_opportunity() -> TradeOpportunity:
    """Return a representative paper-trade opportunity."""
    return TradeOpportunity(
        sportsbook_game_id="game-123",
        kalshi_ticker="KXNFLGAME-TEST-SEA",
        team="Seattle Seahawks",
        contract_side="yes",
        fair_probability=0.63,
        fair_value_cents=63.0,
        market_price_cents=58.0,
        edge_cents=5.0,
        edge_percentage_points=5.0,
        estimated_return_on_cost=5 / 58,
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
# Database initialization
# ---------------------------------------------------------------------


def test_initialize_database_creates_file(
    tmp_path,
) -> None:
    """Initialization should create the SQLite database file."""
    path = tmp_path / "scanner.db"

    assert not path.exists()

    initialize_database(path)

    assert path.exists()


def test_initialize_database_creates_tables(
    database_path,
) -> None:
    """All four project tables should exist."""
    with get_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table';
            """
        ).fetchall()

    table_names = {
        row["name"]
        for row in rows
    }

    assert "sportsbook_games" in table_names
    assert "kalshi_market_snapshots" in table_names
    assert "verified_matches" in table_names
    assert "paper_trade_opportunities" in table_names


def test_initialize_database_can_run_twice(
    database_path,
) -> None:
    """
    Initialization should be idempotent.

    Running it again must not destroy the existing schema.
    """
    initialize_database(database_path)

    statistics = get_database_statistics(
        database_path
    )

    assert statistics == {
        "sportsbook_games": 0,
        "kalshi_market_snapshots": 0,
        "verified_matches": 0,
        "paper_trade_opportunities": 0,
    }


def test_connection_uses_row_factory(
    database_path,
) -> None:
    """
    Query results should support dictionary-style column access.
    """
    with get_connection(database_path) as connection:
        row = connection.execute(
            "SELECT 42 AS answer;"
        ).fetchone()

    assert row is not None
    assert row["answer"] == 42


def test_foreign_keys_are_enabled(
    database_path,
) -> None:
    """Every project connection should enable SQLite foreign keys."""
    with get_connection(database_path) as connection:
        row = connection.execute(
            "PRAGMA foreign_keys;"
        ).fetchone()

    assert row is not None
    assert row[0] == 1


# ---------------------------------------------------------------------
# Sportsbook persistence
# ---------------------------------------------------------------------


def test_save_sportsbook_game(
    database_path,
) -> None:
    """A valid sportsbook game should be stored."""
    observed_at = datetime(
        2026,
        9,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    inserted = save_sportsbook_games(
        games=[
            build_test_game(),
        ],
        observed_at=observed_at,
        database_path=database_path,
    )

    assert inserted == 1

    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM sportsbook_games;
            """
        ).fetchone()

    assert row is not None
    assert row["sportsbook_game_id"] == "game-123"
    assert row["sport_key"] == "americanfootball_nfl"
    assert row["sport_title"] == "NFL"
    assert row["home_team"] == "Seattle Seahawks"
    assert row["away_team"] == "New England Patriots"


def test_sportsbook_raw_json_is_preserved(
    database_path,
) -> None:
    """
    The complete API object should be retained for later analysis.
    """
    game = build_test_game()

    save_sportsbook_games(
        games=[game],
        database_path=database_path,
    )

    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT raw_json
            FROM sportsbook_games;
            """
        ).fetchone()

    assert row is not None

    stored = json.loads(
        row["raw_json"]
    )

    assert stored["id"] == "game-123"
    assert stored["bookmakers"][0]["key"] == "draftkings"


def test_duplicate_sportsbook_snapshot_is_ignored(
    database_path,
) -> None:
    """
    The same game at the same observation time should not be stored twice.
    """
    observed_at = datetime(
        2026,
        9,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    game = build_test_game()

    first = save_sportsbook_games(
        games=[game],
        observed_at=observed_at,
        database_path=database_path,
    )

    second = save_sportsbook_games(
        games=[game],
        observed_at=observed_at,
        database_path=database_path,
    )

    assert first == 1
    assert second == 0

    statistics = get_database_statistics(
        database_path
    )

    assert statistics["sportsbook_games"] == 1


def test_same_game_at_new_time_creates_new_snapshot(
    database_path,
) -> None:
    """
    Historical snapshots should allow the same game to be observed
    at different times.
    """
    game = build_test_game()

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
        [game],
        observed_at=first_time,
        database_path=database_path,
    )

    save_sportsbook_games(
        [game],
        observed_at=second_time,
        database_path=database_path,
    )

    statistics = get_database_statistics(
        database_path
    )

    assert statistics["sportsbook_games"] == 2


def test_invalid_sportsbook_game_is_skipped(
    database_path,
) -> None:
    """A game without an ID should not be persisted."""
    game = build_test_game()
    game["id"] = ""

    inserted = save_sportsbook_games(
        [game],
        database_path=database_path,
    )

    assert inserted == 0


def test_sportsbook_game_without_home_team_is_skipped(
    database_path,
) -> None:
    game = build_test_game()
    game["home_team"] = ""

    inserted = save_sportsbook_games(
        [game],
        database_path=database_path,
    )

    assert inserted == 0


def test_sportsbook_game_without_away_team_is_skipped(
    database_path,
) -> None:
    game = build_test_game()
    game["away_team"] = ""

    inserted = save_sportsbook_games(
        [game],
        database_path=database_path,
    )

    assert inserted == 0


# ---------------------------------------------------------------------
# Kalshi persistence
# ---------------------------------------------------------------------


def test_save_kalshi_market(
    database_path,
) -> None:
    """A valid Kalshi snapshot should be stored."""
    inserted = save_kalshi_markets(
        [build_test_market()],
        database_path=database_path,
    )

    assert inserted == 1

    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM kalshi_market_snapshots;
            """
        ).fetchone()

    assert row is not None

    assert row["kalshi_ticker"] == (
        "KXNFLGAME-TEST-SEA"
    )

    assert row["yes_bid"] == pytest.approx(57)
    assert row["yes_ask"] == pytest.approx(58)
    assert row["no_bid"] == pytest.approx(42)
    assert row["no_ask"] == pytest.approx(43)


def test_kalshi_numeric_strings_are_converted(
    database_path,
) -> None:
    """
    Numeric API fields represented as strings should be stored as numbers.
    """
    market = build_test_market()

    market["yes_bid"] = "57.5"
    market["yes_ask"] = "58.5"
    market["volume"] = "1250.25"

    save_kalshi_markets(
        [market],
        database_path=database_path,
    )

    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT yes_bid, yes_ask, volume
            FROM kalshi_market_snapshots;
            """
        ).fetchone()

    assert row is not None
    assert row["yes_bid"] == pytest.approx(57.5)
    assert row["yes_ask"] == pytest.approx(58.5)
    assert row["volume"] == pytest.approx(1250.25)


def test_invalid_kalshi_numeric_value_becomes_null(
    database_path,
) -> None:
    """
    Malformed optional numeric data should become SQL NULL rather
    than crashing persistence.
    """
    market = build_test_market()
    market["yes_bid"] = "not-a-number"

    save_kalshi_markets(
        [market],
        database_path=database_path,
    )

    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT yes_bid
            FROM kalshi_market_snapshots;
            """
        ).fetchone()

    assert row is not None
    assert row["yes_bid"] is None


def test_market_without_ticker_is_skipped(
    database_path,
) -> None:
    market = build_test_market()
    market["ticker"] = ""

    inserted = save_kalshi_markets(
        [market],
        database_path=database_path,
    )

    assert inserted == 0


def test_duplicate_kalshi_snapshot_is_ignored(
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

    market = build_test_market()

    first = save_kalshi_markets(
        [market],
        observed_at=observed_at,
        database_path=database_path,
    )

    second = save_kalshi_markets(
        [market],
        observed_at=observed_at,
        database_path=database_path,
    )

    assert first == 1
    assert second == 0


def test_same_kalshi_market_at_new_time_creates_snapshot(
    database_path,
) -> None:
    market = build_test_market()

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
        1,
        tzinfo=timezone.utc,
    )

    save_kalshi_markets(
        [market],
        observed_at=first_time,
        database_path=database_path,
    )

    save_kalshi_markets(
        [market],
        observed_at=second_time,
        database_path=database_path,
    )

    statistics = get_database_statistics(
        database_path
    )

    assert statistics[
        "kalshi_market_snapshots"
    ] == 2


# ---------------------------------------------------------------------
# Verified matches
# ---------------------------------------------------------------------


def test_save_verified_match(
    database_path,
) -> None:
    """A valid MarketMatch should be persisted."""
    inserted = save_verified_matches(
        [build_test_match()],
        database_path=database_path,
    )

    assert inserted == 1

    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM verified_matches;
            """
        ).fetchone()

    assert row is not None
    assert row["sportsbook_game_id"] == "game-123"
    assert row["kalshi_ticker"] == "KXNFLGAME-TEST-SEA"
    assert row["yes_team"] == "Seattle Seahawks"
    assert row["no_team"] == "New England Patriots"

    assert row[
        "time_difference_hours"
    ] == pytest.approx(0.25)

    assert row["confidence_score"] == 100


def test_match_reasons_are_serialized(
    database_path,
) -> None:
    match = build_test_match()

    save_verified_matches(
        [match],
        database_path=database_path,
    )

    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT reasons_json
            FROM verified_matches;
            """
        ).fetchone()

    assert row is not None

    reasons = json.loads(
        row["reasons_json"]
    )

    assert reasons == match.reasons


def test_duplicate_verified_match_is_ignored(
    database_path,
) -> None:
    match = build_test_match()

    first = save_verified_matches(
        [match],
        database_path=database_path,
    )

    second = save_verified_matches(
        [match],
        database_path=database_path,
    )

    assert first == 1
    assert second == 0


def test_verified_match_without_game_id_is_skipped(
    database_path,
) -> None:
    match = build_test_match()
    match.sportsbook_game["id"] = ""

    inserted = save_verified_matches(
        [match],
        database_path=database_path,
    )

    assert inserted == 0


def test_verified_match_without_ticker_is_skipped(
    database_path,
) -> None:
    match = build_test_match()
    match.kalshi_market["ticker"] = ""

    inserted = save_verified_matches(
        [match],
        database_path=database_path,
    )

    assert inserted == 0


# ---------------------------------------------------------------------
# Paper-trade opportunities
# ---------------------------------------------------------------------


def test_save_trade_opportunity(
    database_path,
) -> None:
    """A valid paper-trade opportunity should be stored."""
    opportunity = build_test_opportunity()

    inserted = save_trade_opportunities(
        [opportunity],
        database_path=database_path,
    )

    assert inserted == 1

    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM paper_trade_opportunities;
            """
        ).fetchone()

    assert row is not None

    assert row["sportsbook_game_id"] == "game-123"
    assert row["kalshi_ticker"] == "KXNFLGAME-TEST-SEA"
    assert row["team"] == "Seattle Seahawks"
    assert row["contract_side"] == "yes"

    assert row[
        "fair_probability"
    ] == pytest.approx(0.63)

    assert row[
        "fair_value_cents"
    ] == pytest.approx(63)

    assert row[
        "market_price_cents"
    ] == pytest.approx(58)

    assert row["edge_cents"] == pytest.approx(5)

    assert row["status"] == "observed"


def test_trade_opportunity_timestamp_is_preserved(
    database_path,
) -> None:
    opportunity = build_test_opportunity()

    save_trade_opportunities(
        [opportunity],
        database_path=database_path,
    )

    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT observed_at
            FROM paper_trade_opportunities;
            """
        ).fetchone()

    assert row is not None

    assert row["observed_at"] == (
        opportunity.observed_at.isoformat()
    )


def test_duplicate_trade_opportunity_is_ignored(
    database_path,
) -> None:
    opportunity = build_test_opportunity()

    first = save_trade_opportunities(
        [opportunity],
        database_path=database_path,
    )

    second = save_trade_opportunities(
        [opportunity],
        database_path=database_path,
    )

    assert first == 1
    assert second == 0


# ---------------------------------------------------------------------
# Statistics and isolation
# ---------------------------------------------------------------------


def test_empty_database_statistics(
    database_path,
) -> None:
    """A newly initialized database should report all zeros."""
    statistics = get_database_statistics(
        database_path
    )

    assert statistics == {
        "sportsbook_games": 0,
        "kalshi_market_snapshots": 0,
        "verified_matches": 0,
        "paper_trade_opportunities": 0,
    }


def test_statistics_after_inserts(
    database_path,
) -> None:
    """Statistics should reflect persisted records."""
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

    statistics = get_database_statistics(
        database_path
    )

    assert statistics == {
        "sportsbook_games": 1,
        "kalshi_market_snapshots": 1,
        "verified_matches": 1,
        "paper_trade_opportunities": 1,
    }


def test_empty_iterables_insert_nothing(
    database_path,
) -> None:
    """Persistence functions should safely accept empty input."""
    assert save_sportsbook_games(
        [],
        database_path=database_path,
    ) == 0

    assert save_kalshi_markets(
        [],
        database_path=database_path,
    ) == 0

    assert save_verified_matches(
        [],
        database_path=database_path,
    ) == 0

    assert save_trade_opportunities(
        [],
        database_path=database_path,
    ) == 0


def test_temporary_database_is_independent(
    tmp_path,
) -> None:
    """
    Two databases should maintain completely independent state.

    This demonstrates the isolation principle used throughout
    this test suite.
    """
    first_database = (
        tmp_path / "first.db"
    )

    second_database = (
        tmp_path / "second.db"
    )

    initialize_database(first_database)
    initialize_database(second_database)

    save_sportsbook_games(
        [build_test_game()],
        database_path=first_database,
    )

    first_stats = get_database_statistics(
        first_database
    )

    second_stats = get_database_statistics(
        second_database
    )

    assert first_stats["sportsbook_games"] == 1
    assert second_stats["sportsbook_games"] == 0

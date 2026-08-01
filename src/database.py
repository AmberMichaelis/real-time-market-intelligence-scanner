"""
SQLite persistence layer for the market intelligence scanner.

Responsibilities:
- Create the project database and tables.
- Save sportsbook games.
- Save Kalshi market snapshots.
- Save verified market matches.
- Save paper-trade opportunities.
- Provide basic database statistics.

This file does NOT:
- Retrieve API data.
- Calculate probabilities.
- Match markets.
- Place real or simulated orders.
"""

from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from config import DATABASE_PATH
from matcher import MarketMatch
from paper_trader import TradeOpportunity


def utc_now_iso() -> str:
    """
    Return the current UTC time as an ISO-8601 string.

    Example:
        2026-07-30T06:30:00.123456+00:00
    """
    return datetime.now(timezone.utc).isoformat()


def serialize_json(value: Any) -> str:
    """
    Convert a Python value into a compact JSON string.

    Raw API responses are retained so we can inspect or reprocess
    historical data later.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def get_connection(
    database_path: Path = DATABASE_PATH,
) -> sqlite3.Connection:
    """
    Open a configured SQLite database connection.

    Args:
        database_path:
            Location of the SQLite database file.

    Returns:
        An open SQLite connection.

    Notes:
        row_factory allows rows to behave somewhat like dictionaries:

            row["kalshi_ticker"]
    """
    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        database_path,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    # Enforce foreign-key relationships.
    connection.execute(
        "PRAGMA foreign_keys = ON;"
    )

    # WAL allows readers and writers to cooperate more efficiently.
    connection.execute(
        "PRAGMA journal_mode = WAL;"
    )

    return connection


def initialize_database(
    database_path: Path = DATABASE_PATH,
) -> None:
    """
    Create all required database tables and indexes.

    This function is safe to run repeatedly because every table uses
    IF NOT EXISTS.
    """
    schema = """
    CREATE TABLE IF NOT EXISTS sportsbook_games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        sportsbook_game_id TEXT NOT NULL,
        sport_key TEXT,
        sport_title TEXT,

        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL,
        commence_time TEXT,

        observed_at TEXT NOT NULL,
        raw_json TEXT NOT NULL,

        UNIQUE (
            sportsbook_game_id,
            observed_at
        )
    );

    CREATE INDEX IF NOT EXISTS idx_sportsbook_games_external_id
        ON sportsbook_games (sportsbook_game_id);

    CREATE INDEX IF NOT EXISTS idx_sportsbook_games_commence_time
        ON sportsbook_games (commence_time);


    CREATE TABLE IF NOT EXISTS kalshi_market_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        kalshi_ticker TEXT NOT NULL,
        event_ticker TEXT,
        series_ticker TEXT,

        title TEXT,
        subtitle TEXT,
        status TEXT,

        yes_bid REAL,
        yes_ask REAL,
        no_bid REAL,
        no_ask REAL,

        volume REAL,
        liquidity REAL,

        close_time TEXT,
        observed_at TEXT NOT NULL,
        raw_json TEXT NOT NULL,

        UNIQUE (
            kalshi_ticker,
            observed_at
        )
    );

    CREATE INDEX IF NOT EXISTS idx_kalshi_snapshots_ticker
        ON kalshi_market_snapshots (kalshi_ticker);

    CREATE INDEX IF NOT EXISTS idx_kalshi_snapshots_observed_at
        ON kalshi_market_snapshots (observed_at);


    CREATE TABLE IF NOT EXISTS verified_matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        sportsbook_game_id TEXT NOT NULL,
        kalshi_ticker TEXT NOT NULL,

        yes_team TEXT NOT NULL,
        no_team TEXT NOT NULL,

        time_difference_hours REAL NOT NULL,
        confidence_score INTEGER NOT NULL,

        reasons_json TEXT NOT NULL,
        created_at TEXT NOT NULL,

        UNIQUE (
            sportsbook_game_id,
            kalshi_ticker
        )
    );

    CREATE INDEX IF NOT EXISTS idx_verified_matches_game
        ON verified_matches (sportsbook_game_id);

    CREATE INDEX IF NOT EXISTS idx_verified_matches_market
        ON verified_matches (kalshi_ticker);


    CREATE TABLE IF NOT EXISTS paper_trade_opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        sportsbook_game_id TEXT NOT NULL,
        kalshi_ticker TEXT NOT NULL,

        team TEXT NOT NULL,
        contract_side TEXT NOT NULL,

        fair_probability REAL NOT NULL,
        fair_value_cents REAL NOT NULL,
        market_price_cents REAL NOT NULL,

        edge_cents REAL NOT NULL,
        edge_percentage_points REAL NOT NULL,
        estimated_return_on_cost REAL NOT NULL,

        confidence_score INTEGER NOT NULL,
        observed_at TEXT NOT NULL,

        status TEXT NOT NULL DEFAULT 'observed',

        UNIQUE (
            kalshi_ticker,
            contract_side,
            observed_at
        )
    );

    CREATE INDEX IF NOT EXISTS idx_opportunities_ticker
        ON paper_trade_opportunities (kalshi_ticker);

    CREATE INDEX IF NOT EXISTS idx_opportunities_edge
        ON paper_trade_opportunities (edge_cents);

    CREATE INDEX IF NOT EXISTS idx_opportunities_observed_at
        ON paper_trade_opportunities (observed_at);
    """

    with closing(
        get_connection(database_path)
    ) as connection:
        connection.executescript(schema)
        connection.commit()


def _safe_float(
    value: Any,
) -> float | None:
    """
    Convert a value to float when possible.

    Returns None for blank, malformed, or boolean values.
    """
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = value.strip()

        if not cleaned:
            return None

        try:
            return float(cleaned)

        except ValueError:
            return None

    return None


def save_sportsbook_games(
    games: Iterable[dict[str, Any]],
    observed_at: datetime | None = None,
    database_path: Path = DATABASE_PATH,
) -> int:
    """
    Save sportsbook game snapshots.

    Args:
        games:
            Games returned by The Odds API.

        observed_at:
            Shared observation timestamp for this scan.

        database_path:
            SQLite database location.

    Returns:
        Number of rows inserted.

    Notes:
        Every scan creates a new historical snapshot because odds can
        change over time.
    """
    observation_time = (
        observed_at or datetime.now(timezone.utc)
    ).isoformat()

    rows: list[tuple[Any, ...]] = []

    for game in games:
        game_id = game.get("id")
        home_team = game.get("home_team")
        away_team = game.get("away_team")

        if not isinstance(game_id, str) or not game_id:
            continue

        if not isinstance(home_team, str) or not home_team:
            continue

        if not isinstance(away_team, str) or not away_team:
            continue

        rows.append(
            (
                game_id,
                game.get("sport_key"),
                game.get("sport_title"),
                home_team,
                away_team,
                game.get("commence_time"),
                observation_time,
                serialize_json(game),
            )
        )

    if not rows:
        return 0

    statement = """
    INSERT OR IGNORE INTO sportsbook_games (
        sportsbook_game_id,
        sport_key,
        sport_title,
        home_team,
        away_team,
        commence_time,
        observed_at,
        raw_json
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """

    with closing(
        get_connection(database_path)
    ) as connection:
        cursor = connection.executemany(
            statement,
            rows,
        )
        connection.commit()

        return cursor.rowcount


def save_kalshi_markets(
    markets: Iterable[dict[str, Any]],
    observed_at: datetime | None = None,
    database_path: Path = DATABASE_PATH,
) -> int:
    """
    Save Kalshi market snapshots.

    Each execution stores the prices observed during that scan.
    """
    observation_time = (
        observed_at or datetime.now(timezone.utc)
    ).isoformat()

    rows: list[tuple[Any, ...]] = []

    for market in markets:
        ticker = market.get("ticker")

        if not isinstance(ticker, str) or not ticker:
            continue

        rows.append(
            (
                ticker,
                market.get("event_ticker"),
                market.get("series_ticker"),
                market.get("title"),
                market.get("subtitle"),
                market.get("status"),
                _safe_float(market.get("yes_bid")),
                _safe_float(market.get("yes_ask")),
                _safe_float(market.get("no_bid")),
                _safe_float(market.get("no_ask")),
                _safe_float(
                    market.get(
                        "volume",
                        market.get("volume_fp"),
                    )
                ),
                _safe_float(
                    market.get(
                        "liquidity",
                        market.get("liquidity_dollars"),
                    )
                ),
                market.get("close_time"),
                observation_time,
                serialize_json(market),
            )
        )

    if not rows:
        return 0

    statement = """
    INSERT OR IGNORE INTO kalshi_market_snapshots (
        kalshi_ticker,
        event_ticker,
        series_ticker,
        title,
        subtitle,
        status,
        yes_bid,
        yes_ask,
        no_bid,
        no_ask,
        volume,
        liquidity,
        close_time,
        observed_at,
        raw_json
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    with closing(
        get_connection(database_path)
    ) as connection:
        cursor = connection.executemany(
            statement,
            rows,
        )
        connection.commit()

        return cursor.rowcount


def save_verified_matches(
    matches: Iterable[MarketMatch],
    database_path: Path = DATABASE_PATH,
) -> int:
    """
    Save accepted sportsbook-to-Kalshi matches.

    Existing game-and-market pairs are ignored so they are not
    duplicated every time the scanner runs.
    """
    rows: list[tuple[Any, ...]] = []
    created_at = utc_now_iso()

    for match in matches:
        game_id = str(
            match.sportsbook_game.get("id", "")
        ).strip()

        ticker = str(
            match.kalshi_market.get("ticker", "")
        ).strip()

        if not game_id or not ticker:
            continue

        rows.append(
            (
                game_id,
                ticker,
                match.yes_team,
                match.no_team,
                match.time_difference_hours,
                match.confidence_score,
                serialize_json(match.reasons),
                created_at,
            )
        )

    if not rows:
        return 0

    statement = """
    INSERT OR IGNORE INTO verified_matches (
        sportsbook_game_id,
        kalshi_ticker,
        yes_team,
        no_team,
        time_difference_hours,
        confidence_score,
        reasons_json,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """

    with closing(
        get_connection(database_path)
    ) as connection:
        cursor = connection.executemany(
            statement,
            rows,
        )
        connection.commit()

        return cursor.rowcount


def save_trade_opportunities(
    opportunities: Iterable[TradeOpportunity],
    database_path: Path = DATABASE_PATH,
) -> int:
    """
    Save paper-trade opportunities.

    Opportunities are observations only. Saving one does not mean an
    actual trade was placed.
    """
    rows: list[tuple[Any, ...]] = []

    for opportunity in opportunities:
        rows.append(
            (
                opportunity.sportsbook_game_id,
                opportunity.kalshi_ticker,
                opportunity.team,
                opportunity.contract_side,
                opportunity.fair_probability,
                opportunity.fair_value_cents,
                opportunity.market_price_cents,
                opportunity.edge_cents,
                opportunity.edge_percentage_points,
                opportunity.estimated_return_on_cost,
                opportunity.confidence_score,
                opportunity.observed_at.isoformat(),
                "observed",
            )
        )

    if not rows:
        return 0

    statement = """
    INSERT OR IGNORE INTO paper_trade_opportunities (
        sportsbook_game_id,
        kalshi_ticker,
        team,
        contract_side,
        fair_probability,
        fair_value_cents,
        market_price_cents,
        edge_cents,
        edge_percentage_points,
        estimated_return_on_cost,
        confidence_score,
        observed_at,
        status
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    with closing(
        get_connection(database_path)
    ) as connection:
        cursor = connection.executemany(
            statement,
            rows,
        )
        connection.commit()

        return cursor.rowcount


def get_database_statistics(
    database_path: Path = DATABASE_PATH,
) -> dict[str, int]:
    """
    Return row counts for the main database tables.
    """
    table_names = (
        "sportsbook_games",
        "kalshi_market_snapshots",
        "verified_matches",
        "paper_trade_opportunities",
    )

    statistics: dict[str, int] = {}

    with closing(
        get_connection(database_path)
    ) as connection:
        for table_name in table_names:
            # The table names come from a fixed internal tuple rather
            # than user input, so formatting them into SQL is safe.
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM {table_name};"
            ).fetchone()

            statistics[table_name] = (
                int(row["count"])
                if row is not None
                else 0
            )

    return statistics

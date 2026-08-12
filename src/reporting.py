"""
Reporting utilities for the market intelligence scanner.

Responsibilities:
- Read summarized information from the SQLite database.
- Produce human-readable scanner reports.
- Show recent observations and paper-trade opportunities.

This file does NOT:
- Retrieve API data.
- Calculate probabilities.
- Match markets.
- Modify database records.
"""

from contextlib import closing
from pathlib import Path
import sqlite3

from config import DATABASE_PATH
from database import get_connection


def get_table_counts(
    database_path: Path = DATABASE_PATH,
) -> dict[str, int]:
    """
    Return row counts for the major project tables.
    """
    tables = (
        "sportsbook_games",
        "kalshi_market_snapshots",
        "verified_matches",
        "paper_trade_opportunities",
    )

    counts: dict[str, int] = {}

    with closing(
        get_connection(database_path)
    ) as connection:
        for table in tables:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS row_count
                FROM {table};
                """
            ).fetchone()

            counts[table] = (
                int(row["row_count"])
                if row is not None
                else 0
            )

    return counts


def get_latest_sportsbook_observation(
    database_path: Path = DATABASE_PATH,
) -> sqlite3.Row | None:
    """
    Return information about the most recent sportsbook scan.

    Returns:
        Row containing:
        - observed_at
        - game_count

        or None when no sportsbook data exists.
    """
    with closing(
        get_connection(database_path)
    ) as connection:
        return connection.execute(
            """
            SELECT
                observed_at,
                COUNT(*) AS game_count
            FROM sportsbook_games
            GROUP BY observed_at
            ORDER BY observed_at DESC
            LIMIT 1;
            """
        ).fetchone()


def get_latest_kalshi_observation(
    database_path: Path = DATABASE_PATH,
) -> sqlite3.Row | None:
    """
    Return information about the most recent Kalshi scan.
    """
    with closing(
        get_connection(database_path)
    ) as connection:
        return connection.execute(
            """
            SELECT
                observed_at,
                COUNT(*) AS market_count
            FROM kalshi_market_snapshots
            GROUP BY observed_at
            ORDER BY observed_at DESC
            LIMIT 1;
            """
        ).fetchone()


def get_top_opportunities(
    limit: int = 10,
    database_path: Path = DATABASE_PATH,
) -> list[sqlite3.Row]:
    """
    Return the largest paper-trade opportunities recorded so far.

    Args:
        limit:
            Maximum number of opportunities to return.

    Returns:
        Rows sorted from largest to smallest estimated edge.
    """
    if limit < 1:
        raise ValueError(
            "Opportunity limit must be at least 1."
        )

    with closing(
        get_connection(database_path)
    ) as connection:
        rows = connection.execute(
            """
            SELECT
                team,
                kalshi_ticker,
                contract_side,
                fair_probability,
                fair_value_cents,
                market_price_cents,
                edge_cents,
                estimated_return_on_cost,
                confidence_score,
                observed_at
            FROM paper_trade_opportunities
            ORDER BY edge_cents DESC
            LIMIT ?;
            """,
            (limit,),
        ).fetchall()

    return list(rows)


def get_recent_verified_matches(
    limit: int = 10,
    database_path: Path = DATABASE_PATH,
) -> list[sqlite3.Row]:
    """
    Return recently stored sportsbook-to-Kalshi matches.
    """
    if limit < 1:
        raise ValueError(
            "Match limit must be at least 1."
        )

    with closing(
        get_connection(database_path)
    ) as connection:
        rows = connection.execute(
            """
            SELECT
                sportsbook_game_id,
                kalshi_ticker,
                yes_team,
                no_team,
                time_difference_hours,
                confidence_score,
                created_at
            FROM verified_matches
            ORDER BY created_at DESC
            LIMIT ?;
            """,
            (limit,),
        ).fetchall()

    return list(rows)


def build_text_report(
    database_path: Path = DATABASE_PATH,
) -> str:
    """
    Build a human-readable summary of the scanner database.

    Returns:
        Multi-line report string.
    """
    counts = get_table_counts(
        database_path
    )

    sportsbook_latest = get_latest_sportsbook_observation(
        database_path
    )

    kalshi_latest = get_latest_kalshi_observation(
        database_path
    )

    opportunities = get_top_opportunities(
        limit=5,
        database_path=database_path,
    )

    matches = get_recent_verified_matches(
        limit=5,
        database_path=database_path,
    )

    lines: list[str] = []

    lines.append("=" * 72)
    lines.append("REAL-TIME MARKET INTELLIGENCE SCANNER")
    lines.append("=" * 72)
    lines.append("")

    lines.append("DATABASE TOTALS")
    lines.append("-" * 72)

    lines.append(
        "Sportsbook snapshots: "
        f"{counts['sportsbook_games']:,}"
    )

    lines.append(
        "Kalshi market snapshots: "
        f"{counts['kalshi_market_snapshots']:,}"
    )

    lines.append(
        "Verified matches: "
        f"{counts['verified_matches']:,}"
    )

    lines.append(
        "Paper-trade opportunities: "
        f"{counts['paper_trade_opportunities']:,}"
    )

    lines.append("")
    lines.append("LATEST SCAN")
    lines.append("-" * 72)

    if sportsbook_latest is None:
        lines.append(
            "No sportsbook observations have been saved."
        )
    else:
        lines.append(
            "Sportsbook games: "
            f"{sportsbook_latest['game_count']:,}"
        )

        lines.append(
            "Sportsbook observed at: "
            f"{sportsbook_latest['observed_at']}"
        )

    if kalshi_latest is None:
        lines.append(
            "No Kalshi observations have been saved."
        )
    else:
        lines.append(
            "Kalshi markets: "
            f"{kalshi_latest['market_count']:,}"
        )

        lines.append(
            "Kalshi observed at: "
            f"{kalshi_latest['observed_at']}"
        )

    lines.append("")
    lines.append("RECENT VERIFIED MATCHES")
    lines.append("-" * 72)

    if not matches:
        lines.append(
            "No verified sportsbook-to-Kalshi matches "
            "have been recorded yet."
        )

    else:
        for match in matches:
            lines.append(
                f"{match['yes_team']} vs "
                f"{match['no_team']}"
            )

            lines.append(
                f"  Kalshi: {match['kalshi_ticker']}"
            )

            lines.append(
                "  Confidence: "
                f"{match['confidence_score']}/100"
            )

            lines.append(
                "  Time difference: "
                f"{match['time_difference_hours']:.2f} hours"
            )

    lines.append("")
    lines.append("TOP PAPER-TRADE OPPORTUNITIES")
    lines.append("-" * 72)

    if not opportunities:
        lines.append(
            "No paper-trade opportunities have been "
            "recorded yet."
        )

    else:
        for opportunity in opportunities:
            lines.append(
                f"{opportunity['team']} "
                f"({opportunity['contract_side'].upper()})"
            )

            lines.append(
                "  Fair probability: "
                f"{opportunity['fair_probability']:.2%}"
            )

            lines.append(
                "  Fair value: "
                f"{opportunity['fair_value_cents']:.2f}¢"
            )

            lines.append(
                "  Market price: "
                f"{opportunity['market_price_cents']:.2f}¢"
            )

            lines.append(
                "  Edge: "
                f"{opportunity['edge_cents']:.2f}¢"
            )

            lines.append(
                "  Edge relative to cost: "
                f"{opportunity['estimated_return_on_cost']:.2%}"
            )

            lines.append(
                "  Confidence: "
                f"{opportunity['confidence_score']}/100"
            )

    lines.append("")
    lines.append("=" * 72)

    return "\n".join(lines)


def print_report(
    database_path: Path = DATABASE_PATH,
) -> None:
    """
    Print the current scanner report.
    """
    print(
        build_text_report(
            database_path
        )
    )

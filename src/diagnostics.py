"""
Diagnostic tools for investigating market-matching failures.

Responsibilities:
- Find Kalshi markets that mention both sportsbook teams.
- Explain why a possible match was rejected.
- Display representative near-matches for inspection.

This file is for development and debugging. It does not calculate
prices, create trades, or modify data.
"""

from dataclasses import dataclass
from typing import Any

from matcher import (
    build_market_search_text,
    build_team_aliases,
    calculate_time_difference_hours,
    determine_yes_team,
    is_multivariate_market,
    text_contains_alias,
)


@dataclass
class NearMatch:
    """
    Represents a Kalshi market that mentions both sportsbook teams.

    A near-match has passed the basic team-name test but may still fail
    because of an ambiguous YES side, mismatched time, or multileg format.
    """

    sportsbook_game: dict[str, Any]
    kalshi_market: dict[str, Any]
    home_team_found: bool
    away_team_found: bool
    yes_team: str | None
    time_difference_hours: float | None
    is_multivariate: bool
    rejection_reasons: list[str]


def analyze_possible_match(
    sportsbook_game: dict[str, Any],
    kalshi_market: dict[str, Any],
    maximum_time_difference_hours: float = 36,
) -> NearMatch | None:
    """
    Analyze one sportsbook game and one Kalshi market.

    Returns None unless both teams appear somewhere in the Kalshi
    market text. Markets passing that first test are returned with
    detailed rejection reasons.
    """
    home_team = sportsbook_game.get("home_team")
    away_team = sportsbook_game.get("away_team")

    if not isinstance(home_team, str) or not home_team.strip():
        return None

    if not isinstance(away_team, str) or not away_team.strip():
        return None

    market_text = build_market_search_text(kalshi_market)

    home_team_found = text_contains_alias(
        market_text,
        build_team_aliases(home_team),
    )

    away_team_found = text_contains_alias(
        market_text,
        build_team_aliases(away_team),
    )

    # This diagnostic focuses only on markets mentioning both teams.
    if not home_team_found or not away_team_found:
        return None

    multivariate = is_multivariate_market(
        kalshi_market
    )

    yes_team = determine_yes_team(
        home_team=home_team,
        away_team=away_team,
        market=kalshi_market,
    )

    time_difference = calculate_time_difference_hours(
        sportsbook_game=sportsbook_game,
        kalshi_market=kalshi_market,
    )

    rejection_reasons: list[str] = []

    if multivariate:
        rejection_reasons.append(
            "The Kalshi market contains multiple selected legs."
        )

    if yes_team is None:
        rejection_reasons.append(
            "The matcher could not determine which team YES represents."
        )

    if time_difference is None:
        rejection_reasons.append(
            "The event times could not be compared."
        )

    elif time_difference > maximum_time_difference_hours:
        rejection_reasons.append(
            "The event times differ by more than "
            f"{maximum_time_difference_hours:.0f} hours."
        )

    return NearMatch(
        sportsbook_game=sportsbook_game,
        kalshi_market=kalshi_market,
        home_team_found=home_team_found,
        away_team_found=away_team_found,
        yes_team=yes_team,
        time_difference_hours=time_difference,
        is_multivariate=multivariate,
        rejection_reasons=rejection_reasons,
    )


def find_near_matches(
    sportsbook_games: list[dict[str, Any]],
    kalshi_markets: list[dict[str, Any]],
    maximum_time_difference_hours: float = 36,
) -> list[NearMatch]:
    """
    Find Kalshi markets that mention both teams from a sportsbook game.
    """
    near_matches: list[NearMatch] = []

    for sportsbook_game in sportsbook_games:
        for kalshi_market in kalshi_markets:
            result = analyze_possible_match(
                sportsbook_game=sportsbook_game,
                kalshi_market=kalshi_market,
                maximum_time_difference_hours=(
                    maximum_time_difference_hours
                ),
            )

            if result is not None:
                near_matches.append(result)

    return near_matches


def print_near_match_report(
    near_matches: list[NearMatch],
    display_limit: int = 20,
) -> None:
    """
    Print a readable report describing possible matching failures.
    """
    if display_limit < 1:
        raise ValueError(
            "Display limit must be at least 1."
        )

    print()
    print(f"Text-based near matches: {len(near_matches)}")
    print()

    if not near_matches:
        print(
            "No Kalshi markets in the retrieved pages mentioned both "
            "teams from any sportsbook game."
        )
        return

    for near_match in near_matches[:display_limit]:
        game = near_match.sportsbook_game
        market = near_match.kalshi_market

        print("-" * 72)
        print(
            f"Sportsbook game: "
            f"{game.get('away_team')} at "
            f"{game.get('home_team')}"
        )
        print(
            f"Sportsbook time: "
            f"{game.get('commence_time', 'Unknown')}"
        )
        print(
            f"Kalshi ticker: "
            f"{market.get('ticker', 'Unknown')}"
        )
        print(
            f"Kalshi title: "
            f"{market.get('title', 'Untitled')}"
        )
        print(
            f"Kalshi subtitle: "
            f"{market.get('subtitle', '')}"
        )
        print(
            f"YES subtitle: "
            f"{market.get('yes_sub_title', '')}"
        )
        print(
            f"NO subtitle: "
            f"{market.get('no_sub_title', '')}"
        )
        print(
            f"YES team detected: "
            f"{near_match.yes_team or 'Ambiguous'}"
        )

        if near_match.time_difference_hours is None:
            print("Time difference: Unavailable")
        else:
            print(
                "Time difference: "
                f"{near_match.time_difference_hours:.2f} hours"
            )

        if near_match.rejection_reasons:
            print("Rejection reasons:")

            for reason in near_match.rejection_reasons:
                print(f"  - {reason}")
        else:
            print(
                "No rejection reason was detected. "
                "This market should be examined closely."
            )

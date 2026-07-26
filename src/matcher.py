"""
Utilities for matching sportsbook games to Kalshi markets.

Responsibilities:
- Normalize team and market text.
- Identify team names inside Kalshi market descriptions.
- Compare sportsbook and Kalshi event times.
- Determine which team the Kalshi YES contract represents.
- Reject ambiguous, multileg, or low-confidence matches.

This file does NOT:
- Retrieve API data.
- Calculate probabilities.
- Compare prices.
- Place or simulate trades.
- Save information to the database.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import unicodedata
from typing import Any


@dataclass
class MarketMatch:
    """
    Represents one verified sportsbook-to-Kalshi market match.

    Attributes:
        sportsbook_game:
            Raw game dictionary from The Odds API.

        kalshi_market:
            Raw market dictionary from Kalshi.

        yes_team:
            Team represented by purchasing a YES contract.

        no_team:
            Opposing team represented by the NO side.

        time_difference_hours:
            Difference between the sportsbook start time and the
            Kalshi market's relevant event time.

        confidence_score:
            Simple score describing the strength of the match.

        reasons:
            Human-readable explanations for why the match was accepted.
    """

    sportsbook_game: dict[str, Any]
    kalshi_market: dict[str, Any]
    yes_team: str
    no_team: str
    time_difference_hours: float
    confidence_score: int
    reasons: list[str]


def normalize_text(value: Any) -> str:
    """
    Convert text into a consistent form for comparison.

    Normalization includes:
    - Converting values to strings.
    - Converting accented characters into basic characters.
    - Changing text to lowercase.
    - Replacing punctuation with spaces.
    - Collapsing repeated whitespace.

    Example:
        "New-England Patriots!" becomes:
        "new england patriots"

    Args:
        value:
            Value to normalize.

    Returns:
        Normalized text.
    """
    if value is None:
        return ""

    text = str(value)

    # Convert characters such as é into their basic form.
    text = unicodedata.normalize(
        "NFKD",
        text,
    ).encode(
        "ascii",
        "ignore",
    ).decode(
        "ascii"
    )

    text = text.lower()

    # Keep letters and numbers while replacing punctuation with spaces.
    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return " ".join(text.split())


def build_team_aliases(
    team_name: str,
) -> set[str]:
    """
    Build useful search aliases from a sportsbook team name.

    For example:

        "New England Patriots"

    produces aliases including:

        "new england patriots"
        "patriots"

    The complete team name is the strongest alias. The final word is
    useful because Kalshi may use only the nickname.

    Args:
        team_name:
            Full team name from The Odds API.

    Returns:
        Set of normalized team aliases.
    """
    normalized_name = normalize_text(team_name)

    if not normalized_name:
        return set()

    words = normalized_name.split()

    aliases = {
        normalized_name,
    }

    # Add the nickname, such as "patriots" or "seahawks".
    if len(words) >= 2:
        nickname = words[-1]

        # Very short words are more likely to create false matches.
        if len(nickname) >= 3:
            aliases.add(nickname)

    return aliases


def text_contains_alias(
    text: str,
    aliases: set[str],
) -> bool:
    """
    Return True when normalized text contains a complete alias.

    Word-boundary-style matching prevents a short alias from matching
    inside an unrelated longer word.

    Args:
        text:
            Text that has already been normalized.

        aliases:
            Normalized team aliases.

    Returns:
        True when at least one alias is present.
    """
    padded_text = f" {text} "

    return any(
        f" {alias} " in padded_text
        for alias in aliases
        if alias
    )


def build_market_search_text(
    market: dict[str, Any],
) -> str:
    """
    Combine useful Kalshi fields into one searchable string.

    Args:
        market:
            Raw Kalshi market dictionary.

    Returns:
        Normalized market text.
    """
    searchable_fields = (
        market.get("ticker", ""),
        market.get("event_ticker", ""),
        market.get("series_ticker", ""),
        market.get("title", ""),
        market.get("subtitle", ""),
        market.get("yes_sub_title", ""),
        market.get("no_sub_title", ""),
        market.get("rules_primary", ""),
        market.get("rules_secondary", ""),
    )

    combined_text = " ".join(
        str(value)
        for value in searchable_fields
        if value is not None
    )

    return normalize_text(combined_text)


def build_yes_side_text(
    market: dict[str, Any],
) -> str:
    """
    Build text most likely to describe the Kalshi YES outcome.

    The YES subtitle is the strongest source. The title and subtitle
    are included because some markets describe the YES condition there.

    Args:
        market:
            Raw Kalshi market dictionary.

    Returns:
        Normalized YES-side text.
    """
    yes_fields = (
        market.get("yes_sub_title", ""),
        market.get("title", ""),
        market.get("subtitle", ""),
        market.get("rules_primary", ""),
    )

    combined_text = " ".join(
        str(value)
        for value in yes_fields
        if value is not None
    )

    return normalize_text(combined_text)


def is_multivariate_market(
    market: dict[str, Any],
) -> bool:
    """
    Return True when a Kalshi market contains multiple selected legs.

    Multivariate markets resemble parlays or bundled outcomes. They
    should not be matched to a single sportsbook game.
    """
    selected_legs = market.get("mve_selected_legs")

    return (
        isinstance(selected_legs, list)
        and len(selected_legs) > 0
    )


def parse_api_datetime(
    value: Any,
) -> datetime | None:
    """
    Parse an ISO-8601 datetime returned by an API.

    Examples:
        2026-09-10T00:15:00Z
        2026-09-10T00:15:00+00:00

    Args:
        value:
            Datetime value to parse.

    Returns:
        Timezone-aware datetime, or None when parsing fails.
    """
    if not isinstance(value, str):
        return None

    cleaned_value = value.strip()

    if not cleaned_value:
        return None

    # Python's fromisoformat expects +00:00 instead of a trailing Z
    # in some Python versions.
    if cleaned_value.endswith("Z"):
        cleaned_value = f"{cleaned_value[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(cleaned_value)

    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def get_kalshi_event_time(
    market: dict[str, Any],
) -> datetime | None:
    """
    Find the best available event-related time from a Kalshi market.

    The fields are checked in order of preference. Kalshi market
    structures can vary, so not every market contains every field.

    Args:
        market:
            Raw Kalshi market dictionary.

    Returns:
        Parsed datetime, or None when no usable time is available.
    """
    possible_fields = (
        "expected_expiration_time",
        "close_time",
        "expiration_time",
        "latest_expiration_time",
    )

    for field_name in possible_fields:
        parsed_time = parse_api_datetime(
            market.get(field_name)
        )

        if parsed_time is not None:
            return parsed_time

    return None


def calculate_time_difference_hours(
    sportsbook_game: dict[str, Any],
    kalshi_market: dict[str, Any],
) -> float | None:
    """
    Calculate the absolute time difference between two events.

    Args:
        sportsbook_game:
            Raw game from The Odds API.

        kalshi_market:
            Raw Kalshi market.

    Returns:
        Absolute difference in hours, or None if either time is missing.
    """
    game_time = parse_api_datetime(
        sportsbook_game.get("commence_time")
    )

    market_time = get_kalshi_event_time(
        kalshi_market
    )

    if game_time is None or market_time is None:
        return None

    difference = abs(
        market_time - game_time
    )

    return difference.total_seconds() / 3600


def determine_yes_team(
    home_team: str,
    away_team: str,
    market: dict[str, Any],
) -> str | None:
    """
    Determine which sportsbook team the Kalshi YES side represents.

    A team is accepted only when the YES-related text mentions one
    team but not the other.

    Args:
        home_team:
            Sportsbook home team.

        away_team:
            Sportsbook away team.

        market:
            Raw Kalshi market.

    Returns:
        Team represented by YES, or None when ambiguous.
    """
    yes_text = build_yes_side_text(market)

    home_aliases = build_team_aliases(home_team)
    away_aliases = build_team_aliases(away_team)

    home_mentioned = text_contains_alias(
        yes_text,
        home_aliases,
    )

    away_mentioned = text_contains_alias(
        yes_text,
        away_aliases,
    )

    if home_mentioned and not away_mentioned:
        return home_team

    if away_mentioned and not home_mentioned:
        return away_team

    return None


def match_game_to_market(
    sportsbook_game: dict[str, Any],
    kalshi_market: dict[str, Any],
    maximum_time_difference_hours: float = 36,
) -> MarketMatch | None:
    """
    Attempt to match one sportsbook game to one Kalshi market.

    The function is intentionally conservative. It rejects the market
    unless:

    1. It is not a multileg market.
    2. Both sportsbook teams appear in the Kalshi market.
    3. The YES side can be assigned to exactly one team.
    4. The event times are reasonably close.

    Args:
        sportsbook_game:
            Raw game from The Odds API.

        kalshi_market:
            Raw market from Kalshi.

        maximum_time_difference_hours:
            Largest acceptable difference between event times.

    Returns:
        MarketMatch when the evidence is strong enough, otherwise None.
    """
    if maximum_time_difference_hours < 0:
        raise ValueError(
            "Maximum time difference cannot be negative."
        )

    if is_multivariate_market(kalshi_market):
        return None

    home_team = sportsbook_game.get("home_team")
    away_team = sportsbook_game.get("away_team")

    if not isinstance(home_team, str) or not home_team.strip():
        return None

    if not isinstance(away_team, str) or not away_team.strip():
        return None

    market_text = build_market_search_text(
        kalshi_market
    )

    home_aliases = build_team_aliases(home_team)
    away_aliases = build_team_aliases(away_team)

    home_mentioned = text_contains_alias(
        market_text,
        home_aliases,
    )

    away_mentioned = text_contains_alias(
        market_text,
        away_aliases,
    )

    # Requiring both teams greatly reduces false matches involving
    # season markets, player propositions, or similarly named teams.
    if not home_mentioned or not away_mentioned:
        return None

    yes_team = determine_yes_team(
        home_team=home_team,
        away_team=away_team,
        market=kalshi_market,
    )

    if yes_team is None:
        return None

    no_team = (
        away_team
        if yes_team == home_team
        else home_team
    )

    time_difference = calculate_time_difference_hours(
        sportsbook_game,
        kalshi_market,
    )

    # Missing time information is treated as unsafe rather than guessed.
    if time_difference is None:
        return None

    if time_difference > maximum_time_difference_hours:
        return None

    reasons = [
        "Both sportsbook teams appear in the Kalshi market.",
        f"The YES side appears to represent {yes_team}.",
        (
            "The sportsbook and Kalshi event times differ by "
            f"{time_difference:.2f} hours."
        ),
        "The Kalshi market is not a multileg market.",
    ]

    confidence_score = 100

    # A larger time difference is not necessarily incorrect, but it
    # reduces confidence slightly.
    if time_difference > 24:
        confidence_score -= 20

    elif time_difference > 12:
        confidence_score -= 10

    return MarketMatch(
        sportsbook_game=sportsbook_game,
        kalshi_market=kalshi_market,
        yes_team=yes_team,
        no_team=no_team,
        time_difference_hours=time_difference,
        confidence_score=confidence_score,
        reasons=reasons,
    )


def find_matches_for_game(
    sportsbook_game: dict[str, Any],
    kalshi_markets: list[dict[str, Any]],
    maximum_time_difference_hours: float = 36,
) -> list[MarketMatch]:
    """
    Find every acceptable Kalshi match for one sportsbook game.

    Results are sorted from highest to lowest confidence.

    Args:
        sportsbook_game:
            Raw game from The Odds API.

        kalshi_markets:
            Markets retrieved from Kalshi.

        maximum_time_difference_hours:
            Largest acceptable difference between event times.

    Returns:
        List of accepted matches.
    """
    matches: list[MarketMatch] = []

    for market in kalshi_markets:
        match = match_game_to_market(
            sportsbook_game=sportsbook_game,
            kalshi_market=market,
            maximum_time_difference_hours=(
                maximum_time_difference_hours
            ),
        )

        if match is not None:
            matches.append(match)

    return sorted(
        matches,
        key=lambda match: match.confidence_score,
        reverse=True,
    )


def match_all_games(
    sportsbook_games: list[dict[str, Any]],
    kalshi_markets: list[dict[str, Any]],
    maximum_time_difference_hours: float = 36,
) -> list[MarketMatch]:
    """
    Match multiple sportsbook games against multiple Kalshi markets.

    Only the highest-confidence match for each sportsbook game is
    returned. Games with no safe match are skipped.

    Args:
        sportsbook_games:
            Games from The Odds API.

        kalshi_markets:
            Markets from Kalshi.

        maximum_time_difference_hours:
            Largest acceptable difference between event times.

    Returns:
        Best verified matches.
    """
    verified_matches: list[MarketMatch] = []

    used_market_tickers: set[str] = set()

    for sportsbook_game in sportsbook_games:
        possible_matches = find_matches_for_game(
            sportsbook_game=sportsbook_game,
            kalshi_markets=kalshi_markets,
            maximum_time_difference_hours=(
                maximum_time_difference_hours
            ),
        )

        for possible_match in possible_matches:
            market_ticker = str(
                possible_match.kalshi_market.get(
                    "ticker",
                    "",
                )
            )

            # Prevent the same Kalshi market from being assigned to
            # multiple sportsbook games.
            if market_ticker and market_ticker in used_market_tickers:
                continue

            verified_matches.append(
                possible_match
            )

            if market_ticker:
                used_market_tickers.add(
                    market_ticker
                )

            break

    return verified_matches

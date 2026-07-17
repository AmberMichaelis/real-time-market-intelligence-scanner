from statistics import median

"""
Pricing and probability utilities.

This module is responsible for converting sportsbook odds into
probabilities and removing the sportsbook's built-in margin.

This file should NOT:
- Call external APIs.
- Match games across platforms.
- Store data in the database.
- Place or simulate trades.
"""


def american_odds_to_probability(american_odds: int | float) -> float:
    """
    Convert American odds into raw implied probability.

    Positive odds formula:
        probability = 100 / (odds + 100)

    Negative odds formula:
        probability = abs(odds) / (abs(odds) + 100)

    Examples:
        +160 becomes approximately 0.3846, or 38.46%.
        -192 becomes approximately 0.6575, or 65.75%.

    Args:
        american_odds:
            American-style odds, such as +160 or -192.

    Returns:
        The raw implied probability as a decimal between 0 and 1.

    Raises:
        ValueError:
            If the odds are zero.

    Note:
        These probabilities still include the sportsbook's margin,
        commonly called the vig or overround.
    """
    if american_odds == 0:
        raise ValueError("American odds cannot be zero.")

    if american_odds > 0:
        return 100 / (american_odds + 100)

    absolute_odds = abs(american_odds)

    return absolute_odds / (absolute_odds + 100)


def remove_vig_two_way(
    first_probability: float,
    second_probability: float,
) -> tuple[float, float]:
    """
    Remove the sportsbook margin from a two-outcome market.

    Sportsbook probabilities usually add up to more than 1.0 because
    the sportsbook includes a profit margin.

    Example:
        Team A raw probability: 0.3846
        Team B raw probability: 0.6575

        Total: 1.0421

    We normalize each probability by dividing it by the total:

        Team A fair probability = 0.3846 / 1.0421
        Team B fair probability = 0.6575 / 1.0421

    Args:
        first_probability:
            Raw implied probability for the first outcome.

        second_probability:
            Raw implied probability for the second outcome.

    Returns:
        A tuple containing the two normalized fair probabilities.

    Raises:
        ValueError:
            If either probability is invalid or their total is zero.
    """
    if not 0 <= first_probability <= 1:
        raise ValueError(
            "The first probability must be between 0 and 1."
        )

    if not 0 <= second_probability <= 1:
        raise ValueError(
            "The second probability must be between 0 and 1."
        )

    total_probability = first_probability + second_probability

    if total_probability == 0:
        raise ValueError(
            "The total probability cannot be zero."
        )

    first_fair_probability = (
        first_probability / total_probability
    )

    second_fair_probability = (
        second_probability / total_probability
    )

    return first_fair_probability, second_fair_probability


def calculate_two_way_fair_probabilities(
    first_american_odds: int | float,
    second_american_odds: int | float,
) -> tuple[float, float]:
    """
    Convert two American odds prices into fair probabilities.

    This function combines the two main pricing steps:

    1. Convert American odds into raw implied probabilities.
    2. Remove the sportsbook margin.

    Args:
        first_american_odds:
            American odds for the first outcome.

        second_american_odds:
            American odds for the second outcome.

    Returns:
        A tuple containing the fair probability for each outcome.
    """
    first_raw_probability = american_odds_to_probability(
        first_american_odds
    )

    second_raw_probability = american_odds_to_probability(
        second_american_odds
    )

    return remove_vig_two_way(
        first_raw_probability,
        second_raw_probability,
    )


def probability_to_cents(probability: float) -> float:
    """
    Convert a probability into an equivalent contract value in cents.

    Kalshi-style binary contracts are often interpreted as prices
    between 1 and 99 cents.

    Examples:
        0.50 becomes 50.0 cents.
        0.3846 becomes 38.46 cents.

    Args:
        probability:
            Probability expressed as a decimal between 0 and 1.

    Returns:
        The equivalent value in cents.

    Raises:
        ValueError:
            If the probability is outside the valid range.
    """
    if not 0 <= probability <= 1:
        raise ValueError(
            "Probability must be between 0 and 1."
        )

    return probability * 100

def calculate_consensus_probability(
    probabilities: list[float],
) -> float:
    """
    Calculate a consensus probability using the median.

    The median is used instead of the arithmetic mean because it is
    less affected by one sportsbook reporting an unusually high or
    low value.

    Args:
        probabilities:
            Fair probabilities from multiple sportsbooks.

    Returns:
        The median probability.

    Raises:
        ValueError:
            If the list is empty or contains an invalid probability.
    """
    if not probabilities:
        raise ValueError(
            "At least one probability is required."
        )

    for probability in probabilities:
        if not 0 <= probability <= 1:
            raise ValueError(
                "Every probability must be between 0 and 1."
            )

    return median(probabilities)


def calculate_game_consensus(
    game: dict,
) -> dict[str, float]:
    """
    Calculate consensus fair probabilities for both teams in one game.

    This function examines every bookmaker's head-to-head market,
    removes the vig from each bookmaker's prices, and collects the
    resulting fair probabilities by team.

    Args:
        game:
            One raw game dictionary returned by The Odds API.

    Returns:
        A dictionary mapping each team name to its consensus fair
        probability.

        Example:
            {
                "New England Patriots": 0.3782,
                "Seattle Seahawks": 0.6218,
            }

    Raises:
        ValueError:
            If no valid two-way moneyline markets are available.
    """
    probabilities_by_team: dict[str, list[float]] = {}

    # One game may include odds from many sportsbooks.
    for bookmaker in game.get("bookmakers", []):

        # A sportsbook may provide several types of markets.
        for market in bookmaker.get("markets", []):

            # We currently support only the straight winner market.
            if market.get("key") != "h2h":
                continue

            outcomes = market.get("outcomes", [])

            # NFL moneyline markets should have exactly two outcomes.
            if len(outcomes) != 2:
                continue

            first_outcome = outcomes[0]
            second_outcome = outcomes[1]

            first_name = first_outcome.get("name")
            second_name = second_outcome.get("name")
            first_odds = first_outcome.get("price")
            second_odds = second_outcome.get("price")

            # Skip incomplete or malformed API records.
            if (
                not first_name
                or not second_name
                or not isinstance(first_odds, (int, float))
                or not isinstance(second_odds, (int, float))
            ):
                continue

            (
                first_fair_probability,
                second_fair_probability,
            ) = calculate_two_way_fair_probabilities(
                first_odds,
                second_odds,
            )

            probabilities_by_team.setdefault(
                first_name,
                [],
            ).append(first_fair_probability)

            probabilities_by_team.setdefault(
                second_name,
                [],
            ).append(second_fair_probability)

    if len(probabilities_by_team) != 2:
        raise ValueError(
            "The game did not contain valid two-way moneyline data."
        )

    return {
        team_name: calculate_consensus_probability(
            team_probabilities
        )
        for team_name, team_probabilities
        in probabilities_by_team.items()
    }

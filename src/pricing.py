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

"""
Paper-trading and opportunity-analysis utilities.

Responsibilities:
- Compare sportsbook fair probabilities with Kalshi prices.
- Calculate potential pricing edges.
- Represent possible paper trades.
- Reject incomplete or invalid market data.

This file does NOT:
- Retrieve API data.
- Match markets.
- Place real orders.
- Access a Kalshi account.
- Store trades in the database.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from matcher import MarketMatch
from pricing import calculate_game_consensus


@dataclass
class TradeOpportunity:
    """
    Represents a potential paper trade.

    Attributes:
        sportsbook_game_id:
            Unique game identifier from The Odds API.

        kalshi_ticker:
            Unique Kalshi market identifier.

        team:
            Team represented by the proposed contract.

        contract_side:
            Kalshi side being evaluated, currently "yes" or "no".

        fair_probability:
            Sportsbook-derived consensus probability.

        fair_value_cents:
            Fair probability expressed as a price from 0 to 100 cents.

        market_price_cents:
            Current executable Kalshi ask price.

        edge_cents:
            Difference between fair value and market price.

        edge_percentage_points:
            Difference between fair probability and market-implied
            probability, expressed in percentage points.

        estimated_return_on_cost:
            Potential pricing edge divided by the purchase price.

        confidence_score:
            Confidence inherited from the market-matching process.

        observed_at:
            UTC timestamp when the opportunity was calculated.
    """

    sportsbook_game_id: str
    kalshi_ticker: str
    team: str
    contract_side: str
    fair_probability: float
    fair_value_cents: float
    market_price_cents: float
    edge_cents: float
    edge_percentage_points: float
    estimated_return_on_cost: float
    confidence_score: int
    observed_at: datetime


def parse_price_cents(
    value: Any,
) -> float | None:
    """
    Convert an API price value into a validated number of cents.

    Kalshi prices should normally fall between 0 and 100 cents.

    Args:
        value:
            Price value returned by the API.

    Returns:
        Valid price as a float, or None when the value is missing
        or invalid.
    """
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        price = float(value)

    elif isinstance(value, str):
        try:
            price = float(value.strip())

        except ValueError:
            return None

    else:
        return None

    if not 0 <= price <= 100:
        return None

    return price


def calculate_edge_cents(
    fair_value_cents: float,
    market_price_cents: float,
) -> float:
    """
    Calculate how underpriced or overpriced a contract appears.

    Positive edge:
        The contract appears cheaper than its estimated fair value.

    Negative edge:
        The contract appears more expensive than its estimated fair value.

    Example:
        Fair value = 63 cents
        Market price = 58 cents
        Edge = 5 cents
    """
    if not 0 <= fair_value_cents <= 100:
        raise ValueError(
            "Fair value must be between 0 and 100 cents."
        )

    if not 0 <= market_price_cents <= 100:
        raise ValueError(
            "Market price must be between 0 and 100 cents."
        )

    return fair_value_cents - market_price_cents


def calculate_return_on_cost(
    edge_cents: float,
    market_price_cents: float,
) -> float:
    """
    Estimate pricing edge relative to the purchase price.

    Example:
        Edge = 5 cents
        Purchase price = 58 cents

        5 / 58 = approximately 8.62%

    This is not a guaranteed investment return. It only describes
    the estimated pricing advantage relative to the contract cost.
    """
    if market_price_cents <= 0:
        raise ValueError(
            "Market price must be greater than zero."
        )

    return edge_cents / market_price_cents


def get_consensus_probability_for_team(
    sportsbook_game: dict[str, Any],
    team: str,
) -> float | None:
    """
    Retrieve the sportsbook consensus probability for one team.

    Args:
        sportsbook_game:
            Raw game returned by The Odds API.

        team:
            Team whose fair probability is needed.

    Returns:
        Fair probability, or None when the team is missing.
    """
    try:
        consensus = calculate_game_consensus(
            sportsbook_game
        )

    except ValueError:
        return None

    probability = consensus.get(team)

    if not isinstance(probability, (int, float)):
        return None

    probability = float(probability)

    if not 0 <= probability <= 1:
        return None

    return probability


def build_yes_opportunity(
    match: MarketMatch,
) -> TradeOpportunity | None:
    """
    Compare the sportsbook fair value with Kalshi's YES ask.

    The YES ask is the approximate price required to immediately buy
    a YES contract.

    Args:
        match:
            Verified sportsbook-to-Kalshi market match.

    Returns:
        TradeOpportunity when all required information is available,
        otherwise None.
    """
    game = match.sportsbook_game
    market = match.kalshi_market

    fair_probability = get_consensus_probability_for_team(
        sportsbook_game=game,
        team=match.yes_team,
    )

    if fair_probability is None:
        return None

    market_price = parse_price_cents(
        market.get("yes_ask")
    )

    # A zero ask often means no executable offer is currently available,
    # rather than a genuinely free contract.
    if market_price is None or market_price <= 0:
        return None

    fair_value_cents = fair_probability * 100

    edge_cents = calculate_edge_cents(
        fair_value_cents=fair_value_cents,
        market_price_cents=market_price,
    )

    return_on_cost = calculate_return_on_cost(
        edge_cents=edge_cents,
        market_price_cents=market_price,
    )

    sportsbook_game_id = str(
        game.get("id", "")
    )

    kalshi_ticker = str(
        market.get("ticker", "")
    )

    if not sportsbook_game_id or not kalshi_ticker:
        return None

    return TradeOpportunity(
        sportsbook_game_id=sportsbook_game_id,
        kalshi_ticker=kalshi_ticker,
        team=match.yes_team,
        contract_side="yes",
        fair_probability=fair_probability,
        fair_value_cents=fair_value_cents,
        market_price_cents=market_price,
        edge_cents=edge_cents,
        edge_percentage_points=edge_cents,
        estimated_return_on_cost=return_on_cost,
        confidence_score=match.confidence_score,
        observed_at=datetime.now(timezone.utc),
    )


def find_trade_opportunities(
    matches: list[MarketMatch],
    minimum_edge_cents: float = 3,
    minimum_confidence_score: int = 80,
) -> list[TradeOpportunity]:
    """
    Find YES contracts that meet the paper-trading requirements.

    Args:
        matches:
            Verified sportsbook-to-Kalshi matches.

        minimum_edge_cents:
            Minimum estimated pricing edge required.

            Example:
                Fair value = 63 cents
                Ask price = 58 cents
                Edge = 5 cents

        minimum_confidence_score:
            Minimum matching confidence required.

    Returns:
        Opportunities sorted from largest to smallest edge.
    """
    if minimum_edge_cents < 0:
        raise ValueError(
            "Minimum edge cannot be negative."
        )

    if not 0 <= minimum_confidence_score <= 100:
        raise ValueError(
            "Minimum confidence must be between 0 and 100."
        )

    opportunities: list[TradeOpportunity] = []

    for match in matches:
        if match.confidence_score < minimum_confidence_score:
            continue

        opportunity = build_yes_opportunity(
            match
        )

        if opportunity is None:
            continue

        if opportunity.edge_cents < minimum_edge_cents:
            continue

        opportunities.append(
            opportunity
        )

    return sorted(
        opportunities,
        key=lambda opportunity: opportunity.edge_cents,
        reverse=True,
    )

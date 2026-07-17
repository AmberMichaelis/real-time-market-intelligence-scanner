# Coordinates the whole application.

# odds = fetch_football_odds()
# kalshi_markets = fetch_kalshi_markets()
# matches = match_markets(odds, kalshi_markets)
# opportunities = compare_prices(matches)
# save_and_report(opportunities)

"""
Application entry point for calculating NFL consensus prices.
"""

from odds_api_client import get_nfl_odds
from pricing import (
    calculate_game_consensus,
    probability_to_cents,
)


def main() -> None:
    """
    Retrieve NFL odds and display a consensus fair value
    for the first game.
    """
    games = get_nfl_odds()

    print(f"Retrieved {len(games)} games.")

    if not games:
        print("No NFL games were returned.")
        return

    game = games[0]

    print()
    print(f"{game['away_team']} at {game['home_team']}")
    print(f"Start time: {game['commence_time']}")

    try:
        consensus = calculate_game_consensus(game)

    except ValueError as error:
        print(f"Could not calculate consensus: {error}")
        return

    print("\nConsensus fair values:")

    for team_name, fair_probability in consensus.items():
        fair_value = probability_to_cents(
            fair_probability
        )

        print(
            f"  {team_name}: "
            f"{fair_probability:.2%} "
            f"({fair_value:.2f}¢)"
        )


if __name__ == "__main__":
    main()

"""
Temporary entry point used to test project configuration.
"""

# from config import (
#     DATABASE_PATH,
#     DATA_DIR,
#     ENV_FILE,
#     MARKET_MAP_PATH,
#     PROJECT_ROOT,
# )


# def main() -> None:
#     """Print the resolved project paths."""
#     print("Real-Time Market Intelligence Scanner")
#     print(f"Project root: {PROJECT_ROOT}")
#     print(f"Environment file: {ENV_FILE}")
#     print(f"Data directory: {DATA_DIR}")
#     print(f"Database path: {DATABASE_PATH}")
#     print(f"Market map path: {MARKET_MAP_PATH}")


# # This condition makes main() run only when this file is executed directly.
# #
# # It will not automatically run if main.py is imported by another file.
# if __name__ == "__main__":
#     main()

"""
Application entry point for inspecting NFL moneyline data.
"""

# from odds_api_client import get_nfl_odds


# def main() -> None:
#     """Retrieve NFL odds and print bookmaker prices for the first game."""

#     games = get_nfl_odds()

#     print(f"Retrieved {len(games)} games.")

#     if not games:
#         print("No NFL games were returned.")
#         return

#     # Select the first game from the API response.
#     game = games[0]

#     print()
#     print(f"{game['away_team']} at {game['home_team']}")
#     print(f"Start time: {game['commence_time']}")

#     # Each game can contain odds from several sportsbooks.
#     for bookmaker in game.get("bookmakers", []):
#         print()
#         print(f"Bookmaker: {bookmaker['title']}")

#         # A bookmaker can expose multiple market types.
#         # We currently request only the head-to-head moneyline market.
#         for market in bookmaker.get("markets", []):
#             if market.get("key") != "h2h":
#                 continue

#             # Each outcome represents a possible winning team.
#             for outcome in market.get("outcomes", []):
#                 team_name = outcome.get("name")
#                 american_odds = outcome.get("price")

#                 print(f"  {team_name}: {american_odds:+}")
                

# if __name__ == "__main__":
#     main()

"""
Application entry point for testing sportsbook pricing calculations.
"""

# from odds_api_client import get_nfl_odds
# from pricing import (
#     american_odds_to_probability,
#     calculate_two_way_fair_probabilities,
#     probability_to_cents,
# )


# def main() -> None:
#     """
#     Retrieve one NFL game and calculate fair probabilities
#     for each bookmaker.
#     """
#     games = get_nfl_odds()

#     print(f"Retrieved {len(games)} games.")

#     if not games:
#         print("No NFL games were returned.")
#         return

#     game = games[0]

#     print()
#     print(f"{game['away_team']} at {game['home_team']}")
#     print(f"Start time: {game['commence_time']}")

#     for bookmaker in game.get("bookmakers", []):
#         for market in bookmaker.get("markets", []):
#             if market.get("key") != "h2h":
#                 continue

#             outcomes = market.get("outcomes", [])

#             # NFL moneyline markets should contain two outcomes.
#             # We skip malformed or incomplete records.
#             if len(outcomes) != 2:
#                 print(
#                     f"\nSkipping {bookmaker['title']}: "
#                     "expected exactly two outcomes."
#                 )
#                 continue

#             first_outcome = outcomes[0]
#             second_outcome = outcomes[1]

#             first_odds = first_outcome["price"]
#             second_odds = second_outcome["price"]

#             first_raw_probability = (
#                 american_odds_to_probability(first_odds)
#             )

#             second_raw_probability = (
#                 american_odds_to_probability(second_odds)
#             )

#             (
#                 first_fair_probability,
#                 second_fair_probability,
#             ) = calculate_two_way_fair_probabilities(
#                 first_odds,
#                 second_odds,
#             )

#             print()
#             print(f"Bookmaker: {bookmaker['title']}")

#             print(
#                 f"  {first_outcome['name']}: "
#                 f"{first_odds:+}"
#             )
#             print(
#                 f"    Raw implied probability: "
#                 f"{first_raw_probability:.2%}"
#             )
#             print(
#                 f"    Fair probability: "
#                 f"{first_fair_probability:.2%}"
#             )
#             print(
#                 f"    Fair value: "
#                 f"{probability_to_cents(first_fair_probability):.2f}¢"
#             )

#             print(
#                 f"  {second_outcome['name']}: "
#                 f"{second_odds:+}"
#             )
#             print(
#                 f"    Raw implied probability: "
#                 f"{second_raw_probability:.2%}"
#             )
#             print(
#                 f"    Fair probability: "
#                 f"{second_fair_probability:.2%}"
#             )
#             print(
#                 f"    Fair value: "
#                 f"{probability_to_cents(second_fair_probability):.2f}¢"
#             )


# if __name__ == "__main__":
#     main()

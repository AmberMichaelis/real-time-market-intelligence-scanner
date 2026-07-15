<!-- @format -->

# Real-Time Market Intelligence Scanner

A Python-based paper-trading scanner that compares football market prices across sportsbook odds data and Kalshi prediction markets.

## Technologies

This project uses API integration, real-time data analysis, probability conversion, event matching, logging, and risk-aware automated decision systems.

## Phase 1

- Pull football odds from The Odds API
- Pull market data from Kalshi
- Match equivalent football markets
- Convert odds into implied probabilities
- Compare estimated fair value against Kalshi prices
- Generate paper-trading alerts
- Log simulated trades for review

## Architecture

main.py
    Orchestrates application workflow

config.py
    Loads configuration and secrets

odds_api_client.py
    Retrieves sportsbook odds data

kalshi_client.py
    Retrieves Kalshi market data

matcher.py
    Matches equivalent markets

pricing.py
    Calculates implied probabilities and value

paper_trader.py
    Simulates trades

database.py
    Stores historical data and paper trades

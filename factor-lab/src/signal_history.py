"""
signal_history.py — Calculate momentum signals over time.

This module computes momentum scores for each trading day in a given timeframe,
allowing users to see:
- When did strong signals occur?
- How often do signals repeat?
- Did past signals work?
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf


def get_timeframe_days(timeframe: str) -> int:
    """Convert timeframe string to number of days."""
    mapping = {
        "1M": 30,
        "3M": 90,
        "6M": 180,
        "1Y": 365,
        "ALL": 1000,  # effectively all available data
    }
    return mapping.get(timeframe.upper(), 180)


def calculate_momentum_history(
    ticker: str,
    timeframe: str = "6M",
    lookback_days: int = None,
) -> dict:
    """
    Calculate momentum scores for each day in the timeframe.

    Momentum = (Close - SMA_20) / SMA_20 * 100

    Parameters
    ----------
    ticker : str
        Stock ticker
    timeframe : str
        "1M", "3M", "6M", "1Y", "ALL"
    lookback_days : int
        Override timeframe (for flexibility)

    Returns
    -------
    dict with:
    {
        "ticker": "AAPL",
        "timeframe": "6M",
        "history": [
            {"date": "2025-10-01", "price": 150.25, "momentum": 5.2, "sma_20": 148.5},
            ...
        ],
        "current_momentum": 12.5,
        "best_momentum": 25.3,
        "worst_momentum": -15.2,
        "avg_momentum": 2.1,
    }
    """
    try:
        # Determine lookback period
        if lookback_days is None:
            lookback_days = get_timeframe_days(timeframe)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        # Fetch price data
        data = yf.download(ticker, start=start_date, end=end_date, progress=False, interval="1d")

        if data.empty or len(data) < 21:
            return {
                "error": f"Insufficient data for {ticker}",
                "ticker": ticker,
                "timeframe": timeframe,
            }

        # Calculate 20-day SMA
        data["SMA_20"] = data["Close"].rolling(window=20).mean()

        # Calculate momentum: (Price - SMA) / SMA * 100
        data["Momentum"] = (data["Close"] - data["SMA_20"]) / data["SMA_20"] * 100

        # Drop NaN rows (first 20 days won't have SMA)
        data = data.dropna()

        # Build history array
        history = []
        for date, row in data.iterrows():
            history.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "price": round(float(row["Close"]), 2),
                    "momentum": round(float(row["Momentum"]), 2),
                    "sma_20": round(float(row["SMA_20"]), 2),
                }
            )

        if not history:
            return {"error": "No valid history data", "ticker": ticker, "timeframe": timeframe}

        # Calculate statistics
        momentum_values = [h["momentum"] for h in history]
        current_momentum = momentum_values[-1] if momentum_values else 0
        best_momentum = max(momentum_values)
        worst_momentum = min(momentum_values)
        avg_momentum = np.mean(momentum_values)

        return {
            "ticker": ticker,
            "timeframe": timeframe,
            "lookback_days": lookback_days,
            "data_points": len(history),
            "history": history,
            "current_momentum": round(current_momentum, 2),
            "best_momentum": round(best_momentum, 2),
            "worst_momentum": round(worst_momentum, 2),
            "avg_momentum": round(avg_momentum, 2),
            "momentum_std": round(float(np.std(momentum_values)), 2),
            "current_price": round(float(data["Close"].iloc[-1]), 2),
            "period_start": history[0]["date"],
            "period_end": history[-1]["date"],
        }

    except Exception as e:
        return {
            "error": f"Failed to calculate signal history: {str(e)}",
            "ticker": ticker,
            "timeframe": timeframe,
        }


def get_momentum_score_label(momentum: float) -> str:
    """Convert momentum value to label."""
    if momentum > 20:
        return "Very Strong"
    elif momentum > 10:
        return "Strong"
    elif momentum > 5:
        return "Moderate"
    elif momentum > 0:
        return "Weak"
    elif momentum > -5:
        return "Neutral"
    elif momentum > -10:
        return "Weak Negative"
    else:
        return "Strong Negative"

"""
factor_delay.py — Calculate what would have happened with signal delay.

When a user sees a strong momentum signal TODAY, in reality:
1. It takes time to place the order (minutes to hours)
2. It takes time for the order to execute (minutes)
3. It takes time for settlement (T+2 in US markets)

This module shows: "If you had acted N days ago at this same signal,
what would your return be today?"

This teaches users about:
- Signal quality (does it actually work?)
- Implementation lag (markets move while you execute)
- Realistic returns (after accounting for delay)
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf


def calculate_factor_delay_returns(
    ticker: str,
    delays: list = [30, 60, 90],  # 1 month, 2 months, 3 months
    lookback_days: int = 150,  # ~150 calendar days = ~100 trading days
) -> dict:
    """
    Calculate what would have happened if user acted N days ago.

    For each delay period (1M, 2M, 3M), shows:
    - Price N days ago
    - Current price
    - Return % if bought N days ago

    Parameters
    ----------
    ticker : str
        Stock ticker (e.g., "AAPL")
    delays : list
        List of days to look back (default [30, 60, 90] for 1M, 2M, 3M)
    lookback_days : int
        How far back to fetch data (default 150 calendar days = ~100 trading days)

    Returns
    -------
    dict with keys:
    {
        "ticker": "AAPL",
        "current_price": 150.25,
        "delay_1d": {"price": 149.50, "return_pct": 0.50, "days_ago": 1},
        "delay_2d": {"price": 148.75, "return_pct": 1.00, "days_ago": 2},
        "delay_3d": {"price": 147.00, "return_pct": 2.20, "days_ago": 3},
        "best_delay": "delay_1d",  # which delay had best return
        "best_return": 0.50,
    }
    """
    try:
        # Fetch price data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        data = yf.download(ticker, start=start_date, end=end_date, progress=False, interval="1d")

        if data.empty or len(data) < max(delays) + 1:
            return {
                "error": f"Not enough data for {ticker} (need {max(delays) + 1} days, got {len(data)})",
                "ticker": ticker,
            }

        # Get prices
        close_prices = data["Close"]
        current_price = (
            float(close_prices.iloc[-1].item())
            if hasattr(close_prices.iloc[-1], "item")
            else float(close_prices.iloc[-1])
        )

        result = {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "timestamp": close_prices.index[-1].strftime("%Y-%m-%d %H:%M:%S"),
            "delays": {},
        }

        best_return = None
        best_delay_key = None

        # Calculate returns for each delay
        for delay_days in sorted(delays):
            if delay_days >= len(close_prices):
                continue

            # Get price N days ago
            price_n_days_ago = (
                float(close_prices.iloc[-delay_days - 1].item())
                if hasattr(close_prices.iloc[-delay_days - 1], "item")
                else float(close_prices.iloc[-delay_days - 1])
            )

            # Calculate return %
            return_pct = ((current_price - price_n_days_ago) / price_n_days_ago) * 100

            # Create human-readable label (1M, 2M, 3M)
            months = delay_days // 30
            delay_label = f"{months}M" if months >= 1 else f"{delay_days}d"
            delay_key = f"delay_{delay_label}"

            result["delays"][delay_key] = {
                "days_ago": delay_days,
                "label": delay_label,
                "price_then": round(price_n_days_ago, 2),
                "price_now": round(current_price, 2),
                "return_pct": round(return_pct, 2),
                "interpretation": get_return_interpretation(return_pct, delay_days),
            }

            # Track best return
            if best_return is None or return_pct > best_return:
                best_return = return_pct
                best_delay_key = delay_key

        result["best_delay"] = best_delay_key
        result["best_return_pct"] = round(best_return, 2) if best_return is not None else None

        return result

    except Exception as e:
        return {
            "error": f"Failed to calculate factor delay for {ticker}: {str(e)}",
            "ticker": ticker,
        }


def get_return_interpretation(return_pct: float, days: int) -> str:
    """
    Generate a human-readable interpretation of the return.

    Parameters
    ----------
    return_pct : float
        Return percentage (e.g., 2.5 for 2.5%)
    days : int
        Number of days

    Returns
    -------
    str : interpretation text
    """
    if return_pct > 5:
        return f"✅ Strong gain (+{return_pct}% in {days} days)"
    elif return_pct > 1:
        return f"✅ Positive return (+{return_pct}% in {days} days)"
    elif return_pct > -1:
        return f"⚠️  Flat return ({return_pct:+}% in {days} days)"
    elif return_pct > -5:
        return f"❌ Minor loss ({return_pct}% in {days} days)"
    else:
        return f"❌ Significant loss ({return_pct}% in {days} days)"


def add_factor_delay_context(analysis_data: dict) -> dict:
    """
    Add factor delay information to an analysis result.

    This enriches the existing /api/analyze response with delay metrics.
    Shows what would have happened if user acted 1M, 2M, 3M ago.

    Parameters
    ----------
    analysis_data : dict
        Existing analysis result from scorer.py

    Returns
    -------
    dict : enriched analysis data with "factor_delay" key
    """
    ticker = analysis_data.get("ticker")

    if not ticker:
        return analysis_data

    delay_info = calculate_factor_delay_returns(
        ticker,
        delays=[30, 60, 90],  # 1M, 2M, 3M
        lookback_days=150,  # ~150 calendar days = ~100 trading days
    )

    analysis_data["factor_delay"] = delay_info

    return analysis_data

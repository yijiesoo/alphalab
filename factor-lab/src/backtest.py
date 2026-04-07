"""
backtest.py — simulate a monthly-rebalanced long/short portfolio.

THIS IS THE MAIN ENGINE of the backtester. It stitches together:
  data → factors → weights → returns → net-of-cost equity curve

KEY CONCEPT: How the return calculation works
Each day, we hold a set of positions (the current weights). The daily P&L
is the sum of (weight × daily return) across all positions. We accumulate
these daily P&Ls into a cumulative equity curve.

We hold constant weights between rebalances. On a rebalance date, we:
1. Compute the new target weights
2. Compute turnover (= how much we need to trade)
3. Subtract transaction costs from that day's return
4. Start using the new weights going forward

TRANSACTION COST MODEL:
cost_t = cost_bps / 10000 × turnover_t

Example: 10 bps cost, 50% turnover → cost = 0.001 × 0.5 = 0.05% that day.
Over 12 monthly rebalances with 50% average turnover: 0.6% drag per year.
This is optimistic for a real fund but reasonable for an academic backtest.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from src.data import compute_returns, download_prices, get_rebalance_dates
from src.factors import compute_all_factors
from src.portfolio import compute_weights_all_dates, compute_turnover


def run_backtest(
    prices: pd.DataFrame | None = None,
    start: str = "2015-01-01",
    end: str | None = None,
    quantile: float = 0.20,
    cost_bps: float = 10.0,
    factor_weights: dict[str, float] | None = None,
    rebalance_freq: str = "MS",
) -> dict:
    """
    Run the full factor backtest end-to-end.

    Parameters
    ----------
    prices          : pre-loaded price DataFrame. If None, downloads fresh.
    start           : start date for data download (if prices is None)
    end             : end date (if None, uses today)
    quantile        : fraction of universe in long/short book (default 0.20)
    cost_bps        : one-way transaction cost in basis points (default 10)
    factor_weights  : dict weighting individual factors in composite signal
    rebalance_freq  : pandas offset alias for rebalance schedule (default "MS")

    Returns
    -------
    dict with keys:
        "returns"       : pd.Series of daily strategy returns (net of costs)
        "gross_returns" : pd.Series of daily strategy returns (before costs)
        "weights"       : pd.DataFrame of weights on rebalance dates
        "turnover"      : pd.Series of one-way turnover on each rebalance date
        "prices"        : the price matrix used
        "factor"        : pd.DataFrame of composite factor scores
    """
    # -----------------------------------------------------------------------
    # Step 1: Data
    # -----------------------------------------------------------------------
    if prices is None:
        print(f"[backtest] Downloading prices ({start} → {end or 'today'})...")
        prices = download_prices(start=start, end=end)

    returns = compute_returns(prices)  # simple daily returns
    rebalance_dates = get_rebalance_dates(prices, frequency=rebalance_freq)

    print(
        f"[backtest] Universe: {prices.shape[1]} stocks, "
        f"{prices.shape[0]} trading days, "
        f"{len(rebalance_dates)} rebalance dates"
    )

    # Get market (SPY) returns for beta calculation
    try:
        spy_prices = download_prices(start=start, end=end, tickers=["SPY"])
        market_returns = compute_returns(spy_prices)["SPY"] if "SPY" in spy_prices.columns else None
    except Exception:
        market_returns = None
        print("[backtest] Warning: Could not fetch SPY for beta calculation")

    # -----------------------------------------------------------------------
    # Step 2: Factors
    # IMPORTANT: We shift the composite factor by 1 day here.
    # This ensures that on rebalance date T, we use factor scores computed
    # from data up to T-1 only. Without this shift, the factor score on
    # date T would use the closing price of date T — which we cannot know
    # until the market closes, i.e. AFTER we would need to trade.
    # -----------------------------------------------------------------------
    print("[backtest] Computing factors...")
    composite, individual_factors = compute_all_factors(
        prices, returns, factor_weights=factor_weights
    )

    # THE CRITICAL SHIFT — prevents look-ahead bias
    # factor_shifted.loc[T] = scores computed from data up to T-1
    factor_shifted = composite.shift(1)

    # -----------------------------------------------------------------------
    # Step 3: Portfolio weights on each rebalance date
    # -----------------------------------------------------------------------
    print("[backtest] Computing weights...")
    weights_on_rebalance = compute_weights_all_dates(
        factor_shifted, rebalance_dates, quantile=quantile
    )

    # -----------------------------------------------------------------------
    # Step 4: Expand weights to daily frequency
    # weights_daily.loc[T] = weights in force on trading day T
    # We forward-fill from each rebalance date until the next one.
    # -----------------------------------------------------------------------
    weights_daily = weights_on_rebalance.reindex(prices.index).ffill()
    weights_daily = weights_daily.fillna(0.0)

    # Align columns: ensure returns and weights have the same tickers
    common_tickers = weights_daily.columns.intersection(returns.columns)
    weights_daily = weights_daily[common_tickers]
    returns_aligned = returns[common_tickers]

    # -----------------------------------------------------------------------
    # Step 5: Daily portfolio returns (gross, before costs)
    # port_return_t = sum_i( weight_{i,t} × return_{i,t} )
    # -----------------------------------------------------------------------
    # Multiply weights (lagged 1 day — we hold yesterday's weights today)
    # by today's returns, then sum across stocks
    weights_lagged = weights_daily.shift(1)  # positions set at yesterday's close
    gross_returns = (weights_lagged * returns_aligned).sum(axis=1)

    # -----------------------------------------------------------------------
    # Step 6: Transaction costs on rebalance dates
    # -----------------------------------------------------------------------
    print("[backtest] Applying transaction costs...")
    cost_series = pd.Series(0.0, index=prices.index)
    turnover_series = pd.Series(0.0, index=rebalance_dates)

    prev_weights = pd.Series(dtype=float)

    for i, date in enumerate(rebalance_dates):
        if date not in weights_on_rebalance.index:
            continue

        curr_weights = weights_on_rebalance.loc[date]

        if i == 0:
            # First rebalance: assume we start from cash (all zeros)
            turnover = curr_weights.abs().sum() / 2.0
        else:
            turnover = compute_turnover(curr_weights, prev_weights)

        turnover_series[date] = turnover

        # Cost = fraction × cost_bps (convert bps to decimal: /10000)
        cost = turnover * (cost_bps / 10_000)
        cost_series[date] = cost

        prev_weights = curr_weights.copy()

    # Net returns = gross returns minus costs on rebalance days
    net_returns = gross_returns - cost_series

    print("[backtest] Done.")

    return {
        "returns": net_returns,
        "gross_returns": gross_returns,
        "market_returns": market_returns,  # Added for beta calculation
        "weights": weights_on_rebalance,
        "turnover": turnover_series,
        "prices": prices,
        "factor": composite,
        "individual_factors": individual_factors,
    }


if __name__ == "__main__":
    results = run_backtest(start="2018-01-01", cost_bps=10)

    cumulative = (1 + results["returns"]).cumprod()
    print(f"\nFinal portfolio value (starting from $1): ${cumulative.iloc[-1]:.4f}")
    print(f"Average monthly turnover: {results['turnover'].mean():.1%}")


def run_single_ticker_backtest(
    ticker: str,
    log_fn: Callable[[str], None] | None = None,
    start: str = "2015-01-01",
    end: str | None = None,
    quantile: float = 0.20,
    cost_bps: float = 10.0,
) -> dict:
    """
    Run the factor backtest for a *single* ticker universe and stream
    progress messages via *log_fn*.

    This is a simplified variant of :func:`run_backtest` designed for use
    with the ``/api/backtest/stream`` SSE endpoint.  The single ticker is
    combined with the default large-cap universe so that cross-sectional
    factor z-scores remain meaningful.

    Parameters
    ----------
    ticker   : equity symbol to focus on, e.g. ``"NVDA"``
    log_fn   : callable that receives one progress string per step; if
               ``None`` progress is printed to stdout
    start    : backtest start date (ISO format)
    end      : backtest end date or ``None`` for today
    quantile : long/short quantile fraction (default 0.20)
    cost_bps : one-way transaction cost in basis points (default 10)

    Returns
    -------
    dict — same structure as :func:`run_backtest`
    """
    if log_fn is None:
        log_fn = print

    log_fn(f"[stream] Starting single-ticker backtest for {ticker} ...")

    log_fn(f"[stream] Downloading prices ({start} → {end or 'today'}) ...")
    prices = download_prices(start=start, end=end)

    if ticker not in prices.columns:
        log_fn(
            f"[stream] WARNING: {ticker} not found in downloaded universe; "
            "proceeding with full universe."
        )

    log_fn(f"[stream] Universe: {prices.shape[1]} stocks, " f"{prices.shape[0]} trading days.")

    log_fn("[stream] Computing factors ...")
    log_fn("[stream] Computing portfolio weights ...")
    log_fn("[stream] Applying transaction costs ...")

    results = run_backtest(
        prices=prices,
        start=start,
        end=end,
        quantile=quantile,
        cost_bps=cost_bps,
    )

    cum_ret = (1 + results["returns"]).cumprod().iloc[-1]
    log_fn(f"[stream] Done. Final portfolio value from $1: ${cum_ret:.4f}")
    log_fn(f"[stream] Average monthly turnover: {results['turnover'].mean():.1%}")

    return results

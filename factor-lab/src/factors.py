"""
factors.py — compute cross-sectional factor signals.

KEY CONCEPT: A "factor" is just a number we compute for each stock that
we believe predicts future returns. The higher the factor score, the more
we want to be long (or short) that stock.

CRITICAL RULE — NO LOOK-AHEAD BIAS:
Every factor must only use data available *before* the decision date.
For a rebalance on date T, we may only use prices up to and including T.
In practice, we shift signals forward by 1 day (.shift(1)) so the factor
computed on day T-1 is used to trade on day T.

If you forget to shift: your backtest will appear to have perfect foresight
and will show incredible (impossible) returns. This is the most common
mistake in quant backtesting.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Momentum 12-1
# ---------------------------------------------------------------------------

def momentum_12_1(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the 12-month minus 1-month momentum signal.

    Definition: return from 252 trading days ago to 21 trading days ago.
    We deliberately skip the most recent month (last 21 days) because:
    - Short-term returns (< 1 month) tend to *reverse*, not continue.
    - Including the last month would mix the momentum effect with the
      short-term reversal effect, weakening the signal.

    Parameters
    ----------
    prices : DataFrame of adjusted close prices (rows=dates, cols=tickers)

    Returns
    -------
    DataFrame of raw momentum scores (same shape as prices).
    Will contain NaN for the first 252 rows — not enough history.

    THEN: always call cross_sectional_zscore() on the output before
    feeding it to portfolio construction.
    """
    # Price 252 trading days ago (approximately 12 months)
    price_12m_ago = prices.shift(252)

    # Price 21 trading days ago (approximately 1 month — the skip)
    price_1m_ago = prices.shift(21)

    # Momentum = return over the formation window
    # Formula: (P_{t-21} - P_{t-252}) / P_{t-252}
    mom = (price_1m_ago - price_12m_ago) / price_12m_ago

    return mom


# ---------------------------------------------------------------------------
# Low Volatility
# ---------------------------------------------------------------------------

def low_volatility(returns: pd.DataFrame, window: int = 63) -> pd.DataFrame:
    """
    Compute trailing volatility over a rolling window.

    We use 63 trading days ≈ 3 calendar months as the lookback.
    Volatility is measured as the standard deviation of daily returns,
    annualised by multiplying by sqrt(252).

    NOTE: We return *negative* volatility so that higher scores = better
    (lower vol). This makes all factors point in the same direction:
    high score = more attractive for the long book.

    Parameters
    ----------
    returns : DataFrame of simple daily returns
    window  : rolling window in trading days (default 63 ≈ 3 months)

    Returns
    -------
    DataFrame of negative annualised volatility scores.
    NaN for first `window` rows.
    """
    # Rolling std of daily returns, then annualise
    vol = returns.rolling(window=window).std() * np.sqrt(252)

    # Negate: we want LOW vol = HIGH score
    return -vol


# ---------------------------------------------------------------------------
# Cross-sectional z-scoring
# ---------------------------------------------------------------------------

def cross_sectional_zscore(factor: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise factor scores across the universe on each date.

    For each row (date), subtract the cross-sectional mean and divide by
    the cross-sectional standard deviation.

    z_score_{i,t} = (factor_{i,t} - mean_t) / std_t

    WHY z-score and not just rank?
    - Ranks are uniform [0, 1] regardless of how spread out the raw signal is.
    - Z-scores preserve information about extremes — a stock 3 std above the
      mean gets a higher score than one just 1 std above.
    - More importantly, z-scoring lets you *combine* multiple factors by
      simply averaging z-scores. Different factors have different units
      (momentum is a return, vol is annualised std) — z-scoring puts them
      on the same scale.

    Returns
    -------
    DataFrame of z-scores, same shape as input.
    """
    mean = factor.mean(axis=1)   # cross-sectional mean per row
    std = factor.std(axis=1)     # cross-sectional std per row

    # Handle edge case: if all stocks have the same factor score on a day,
    # std = 0. Replace with 1.0 so that z-score = (score - mean) / 1 = 0
    # for all stocks (neutral weights). This avoids division by zero NaN.
    std = std.replace(0.0, 1.0)

    # Subtract mean and divide by std — broadcast over columns
    zscores = factor.sub(mean, axis=0).div(std, axis=0)
    return zscores


# ---------------------------------------------------------------------------
# Factor combination
# ---------------------------------------------------------------------------

def combine_factors(
    factor_dict: dict[str, pd.DataFrame],
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Combine multiple z-scored factors into a single composite signal.

    Parameters
    ----------
    factor_dict : dict mapping factor name → z-scored DataFrame
                  e.g. {"momentum": mom_z, "low_vol": vol_z}
    weights     : dict mapping factor name → weight (must sum to 1).
                  If None, equal-weight all factors.

    IMPORTANT: All factors must be z-scored before combining.
    Adding raw momentum (a return) to raw volatility (std of returns)
    is mathematically meaningless.

    Returns
    -------
    DataFrame of composite z-scores.
    """
    names = list(factor_dict.keys())

    if weights is None:
        # Equal weight by default
        weights = {name: 1.0 / len(names) for name in names}

    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError(f"Factor weights must sum to 1. Got: {sum(weights.values()):.4f}")

    # Start with zeros, then accumulate weighted factors
    composite = pd.DataFrame(0.0, index=list(factor_dict.values())[0].index,
                             columns=list(factor_dict.values())[0].columns)
    for name, df in factor_dict.items():
        composite += df * weights[name]

    return composite


# ---------------------------------------------------------------------------
# Convenience wrapper: compute all factors in one call
# ---------------------------------------------------------------------------

def compute_all_factors(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    factor_weights: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """
    Compute and combine all factors. Returns:
    - composite : the combined z-scored signal (use this for portfolio construction)
    - individual : dict of individual z-scored factors (use for diagnostics / IC analysis)

    Parameters
    ----------
    prices          : adjusted close prices
    returns         : simple daily returns (from data.compute_returns)
    factor_weights  : optional custom weights e.g. {"momentum": 0.6, "low_vol": 0.4}
    """
    # Compute raw signals
    mom_raw = momentum_12_1(prices)
    vol_raw = low_volatility(returns)

    # Normalise cross-sectionally
    mom_z = cross_sectional_zscore(mom_raw)
    vol_z = cross_sectional_zscore(vol_raw)

    individual = {
        "momentum": mom_z,
        "low_vol": vol_z,
    }

    composite = combine_factors(individual, weights=factor_weights)

    return composite, individual


if __name__ == "__main__":
    # Quick smoke test
    from factor_lab.data import download_prices, compute_returns

    prices = download_prices(start="2019-01-01")
    returns = compute_returns(prices)

    composite, individual = compute_all_factors(prices, returns)

    print("Composite factor (last 3 rows):")
    print(composite.tail(3).round(3))
    print(f"\nMomentum NaN count (should decrease after first 252 rows): "
          f"{individual['momentum'].isna().sum(axis=1).iloc[-1]} stocks with NaN")

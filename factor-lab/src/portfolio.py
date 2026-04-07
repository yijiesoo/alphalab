"""
portfolio.py — turn factor scores into portfolio weights.

KEY CONCEPT: Dollar-neutral long/short portfolio
- We go LONG the top-scoring stocks (high factor score = attractive)
- We go SHORT the bottom-scoring stocks (low factor score = unattractive)
- "Dollar neutral" means we invest the same dollar amount on each side.
  Long book sums to +1 (100% long), short book sums to -1 (100% short).
  Gross exposure = 2 (200% of capital deployed total).

WHY dollar neutral?
A dollar-neutral portfolio removes most of the market (beta) exposure.
If the whole market crashes, our longs fall and our shorts rise — ideally
they cancel out. We're betting on RELATIVE performance, not direction.
This is what "market neutral" means in hedge fund context.

PERFORMANCE GOAL:
We want to make money from the SPREAD between the long and short books.
If our factor is good, the longs should outperform the shorts regardless
of what the broad market does.
"""

import numpy as np
import pandas as pd


def compute_weights(
    factor_scores: pd.Series,
    quantile: float = 0.20,
) -> pd.Series:
    """
    Convert cross-sectional factor scores into portfolio weights for one date.

    Algorithm:
    1. Rank all stocks by factor score (high score = rank 1)
    2. Long = top `quantile` fraction of stocks
    3. Short = bottom `quantile` fraction of stocks
    4. Equal-weight within each book
    5. Scale so longs sum to +1, shorts sum to -1

    Parameters
    ----------
    factor_scores : Series of factor z-scores for all tickers on one date
    quantile      : fraction of universe in each book (default 0.20 = top/bot 20%)

    Returns
    -------
    Series of portfolio weights. Positive = long, negative = short.
    Stocks in the middle get weight 0 (not held).

    EXAMPLE:
    Universe of 50 stocks, quantile=0.20 → top 10 stocks are long (+0.10 each),
    bottom 10 stocks are short (-0.10 each), middle 30 stocks have weight 0.
    Long sum = 1.0, short sum = -1.0, gross = 2.0.
    """
    # Drop NaN scores — stocks without enough history to compute the factor
    valid = factor_scores.dropna()

    if len(valid) < 10:
        # Not enough stocks to form a meaningful portfolio
        return pd.Series(dtype=float)

    n_stocks = len(valid)
    n_per_book = max(1, int(np.floor(n_stocks * quantile)))

    # Sort by score: highest first
    ranked = valid.sort_values(ascending=False)

    long_tickers = ranked.index[:n_per_book]
    short_tickers = ranked.index[-n_per_book:]

    # Initialise all weights at 0
    weights = pd.Series(0.0, index=valid.index)

    # Equal weight within each book, scaled so each book sums to ±1
    weights[long_tickers] = 1.0 / n_per_book  # +0.1 each if 10 stocks
    weights[short_tickers] = -1.0 / n_per_book  # -0.1 each if 10 stocks

    return weights


def compute_weights_all_dates(
    factor_scores: pd.DataFrame,
    rebalance_dates: pd.DatetimeIndex,
    quantile: float = 0.20,
) -> pd.DataFrame:
    """
    Compute portfolio weights on each rebalance date.

    Parameters
    ----------
    factor_scores    : DataFrame of z-scores (rows=dates, cols=tickers)
    rebalance_dates  : dates on which we rebalance (from data.get_rebalance_dates)
    quantile         : fraction in long / short book

    Returns
    -------
    DataFrame of weights on rebalance dates only (sparse — mostly 0).
    Rows = rebalance dates, cols = tickers.

    IMPORTANT: On the rebalance date T, we use the factor score as of T.
    The actual TRADES happen at the close of T (or open of T+1 if you
    choose next-open execution). The returns accrue from T to T+1_rebalance.

    ALSO IMPORTANT: We already shifted factor signals by 1 day in factors.py
    before this function is called. So the "score on date T" is actually
    derived from data up to T-1. This prevents look-ahead bias.
    """
    weights_list = []

    for date in rebalance_dates:
        if date not in factor_scores.index:
            continue

        scores_today = factor_scores.loc[date]
        w = compute_weights(scores_today, quantile=quantile)
        w.name = date
        weights_list.append(w)

    if not weights_list:
        raise ValueError("No valid rebalance dates found in factor score index.")

    weights_df = pd.DataFrame(weights_list).fillna(0.0)
    return weights_df


def compute_turnover(
    weights_new: pd.Series,
    weights_old: pd.Series,
) -> float:
    """
    Compute one-way turnover between two consecutive weight vectors.

    Turnover = sum(|w_new - w_old|) / 2

    Dividing by 2 converts from total absolute change to one-way traded
    (buying $X and selling $X is one trade, not two).

    Interpretation: turnover of 0.5 means 50% of the portfolio was traded.
    Monthly turnover of 50% → 600% annual turnover → very expensive to run.

    Parameters
    ----------
    weights_new : target weights after rebalance
    weights_old : current weights before rebalance

    Returns
    -------
    Scalar turnover as a fraction of gross exposure.
    """
    # Align on the same tickers, filling missing with 0 (not held)
    all_tickers = weights_new.index.union(weights_old.index)
    w_new = weights_new.reindex(all_tickers).fillna(0.0)
    w_old = weights_old.reindex(all_tickers).fillna(0.0)

    turnover = (w_new - w_old).abs().sum() / 2.0
    return turnover


if __name__ == "__main__":
    # Smoke test with fake data
    np.random.seed(42)
    tickers = [f"STOCK_{i}" for i in range(50)]
    fake_scores = pd.Series(np.random.randn(50), index=tickers)

    weights = compute_weights(fake_scores, quantile=0.20)

    print(f"Long positions:  {(weights > 0).sum()} stocks, sum = {weights[weights > 0].sum():.4f}")
    print(f"Short positions: {(weights < 0).sum()} stocks, sum = {weights[weights < 0].sum():.4f}")
    print(f"Gross exposure:  {weights.abs().sum():.4f} (should be 2.0)")

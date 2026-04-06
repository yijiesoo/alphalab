"""
metrics.py — compute performance and risk metrics from a return series.

ALL METRICS here are standard quant finance concepts. Learn these cold:
they appear in every performance report, job interview, and paper.

REFERENCE FORMULAS:
- CAGR   : Compound Annual Growth Rate — the constant rate that would
            produce the same ending value. Geometric mean of returns.
- Sharpe : Risk-adjusted return. How many units of return per unit of risk.
            > 0.5 is interesting, > 1.0 is good, > 2.0 is exceptional.
- MDD    : Maximum Drawdown — the largest peak-to-trough decline.
            A measure of "how bad does it get in the worst case?"
- IC     : Information Coefficient — rank correlation between factor scores
            and forward returns. A positive IC means the factor has
            genuine predictive power.
"""

import numpy as np
import pandas as pd
from scipy import stats


def compute_cagr(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    COMMENTED OUT: CAGR calculation disabled.
    Compound Annual Growth Rate.

    Formula:
    CAGR = (terminal_value / initial_value)^(1 / years) - 1
         = (1 + r_1) × (1 + r_2) × ... × (1 + r_T))^(252/T) - 1

    where T = number of trading days.

    Parameters
    ----------
    returns          : daily return series (simple, not log)
    periods_per_year : 252 for daily, 12 for monthly

    Returns
    -------
    CAGR as a decimal (e.g. 0.12 = 12% per year)
    """
    # CAGR calculation disabled - returns 0.0
    return 0.0
    
    # Original implementation (commented out):
    # total_return = (1 + returns).prod()
    # n_years = len(returns) / periods_per_year
    # cagr = total_return ** (1.0 / n_years) - 1.0
    # return float(cagr)


def compute_sharpe(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    Annualised Sharpe Ratio.

    Formula:
    Sharpe = (mean_daily_excess_return / std_daily_excess_return) × sqrt(252)

    We use risk_free_rate=0 by default because for a dollar-neutral
    long/short portfolio, the capital isn't actually deployed (it's
    offset by margin) and the risk-free discussion is complex.
    For a long-only strategy, set risk_free_rate to the T-bill rate.

    Parameters
    ----------
    returns          : daily return series
    risk_free_rate   : annualised risk-free rate (default 0)
    periods_per_year : 252 for daily data

    Returns
    -------
    Annualised Sharpe ratio (float).
    """
    daily_rf = risk_free_rate / periods_per_year
    excess = returns - daily_rf
    if excess.std() == 0:
        return 0.0
    sharpe = (excess.mean() / excess.std()) * np.sqrt(periods_per_year)
    return float(sharpe)


def compute_max_drawdown(returns: pd.Series) -> float:
    """
    Maximum Drawdown (MDD).

    The largest peak-to-trough decline in the cumulative equity curve.

    Method:
    1. Build cumulative equity curve: wealth = (1 + r_1)(1 + r_2)...
    2. Track the rolling maximum (the "high water mark")
    3. Drawdown at each date = (current value - peak) / peak
    4. MDD = minimum drawdown (most negative value)

    Example:
    If portfolio grows from $1 to $1.50 then drops to $1.20,
    the drawdown from peak = (1.20 - 1.50) / 1.50 = -20%.

    Returns
    -------
    MDD as a negative decimal (e.g. -0.25 = -25% drawdown).
    """
    equity = (1 + returns).cumprod()
    rolling_max = equity.cummax()                   # high water mark
    drawdown = (equity - rolling_max) / rolling_max  # negative numbers
    max_drawdown = float(drawdown.min())
    return max_drawdown


def compute_underwater_curve(returns: pd.Series) -> pd.Series:
    """
    The full drawdown time series (useful for plotting).

    Returns a Series where 0 = at all-time high, -0.2 = 20% below peak.
    """
    equity = (1 + returns).cumprod()
    rolling_max = equity.cummax()
    underwater = (equity - rolling_max) / rolling_max
    return underwater


def compute_monthly_hit_rate(returns: pd.Series) -> float:
    """
    Fraction of calendar months with positive returns.

    A hit rate above 0.50 means you make money more months than you lose.
    For a good factor strategy, aim for 0.55–0.65.
    """
    monthly = returns.resample("ME").apply(lambda r: (1 + r).prod() - 1)
    hit_rate = float((monthly > 0).mean())
    return hit_rate


def compute_beta(
    returns: pd.Series,
    market_returns: pd.Series,
) -> float:
    """
    Beta — sensitivity to market moves.

    A dollar-neutral long/short portfolio should have beta near 0.
    If beta is 0.3, that means 30% of your returns come from market exposure,
    not from the factor. This is called "beta leakage."

    Formula: beta = cov(strategy, market) / var(market)

    Parameters
    ----------
    returns        : daily strategy returns
    market_returns : daily market (e.g. SPY) returns

    Returns
    -------
    Beta (float). 0 = market neutral, 1 = same as market.
    """
    aligned = pd.DataFrame({"strat": returns, "mkt": market_returns}).dropna()
    if len(aligned) < 30:
        return float("nan")
    slope, _, _, _, _ = stats.linregress(aligned["mkt"], aligned["strat"])
    return float(slope)


def compute_information_coefficient(
    factor_scores: pd.DataFrame,
    forward_returns: pd.DataFrame,
    horizon: int = 21,
) -> pd.Series:
    """
    Information Coefficient (IC) — the key diagnostic for factor quality.

    For each date, compute the rank correlation (Spearman) between:
    - the cross-sectional factor z-scores on that date
    - the forward `horizon`-day returns that follow

    A positive IC means: stocks with higher factor scores tended to have
    higher returns over the next month. This is what we hope for.

    Interpretation:
    - IC > 0.05 consistently → factor has real signal
    - IC t-stat > 2.0 → statistically significant (rough rule of thumb)
    - IC time series should be stable, not all coming from a few lucky months

    Parameters
    ----------
    factor_scores   : DataFrame of factor z-scores (rows=dates, cols=tickers)
    forward_returns : DataFrame of simple returns (same shape)
    horizon         : forward return window in trading days (default 21 ≈ 1 month)

    Returns
    -------
    pd.Series of daily IC values (NaN on dates without enough data).
    """
    fwd_ret = forward_returns.shift(-horizon)  # shift backward to align

    ic_values = {}
    for date in factor_scores.index:
        scores = factor_scores.loc[date].dropna()
        fwd = fwd_ret.loc[date].dropna()

        # Only score tickers that have both factor and forward return
        common = scores.index.intersection(fwd.index)
        if len(common) < 10:
            continue

        corr, _ = stats.spearmanr(scores[common], fwd[common])
        ic_values[date] = corr

    return pd.Series(ic_values)


def compute_ic_summary(ic_series: pd.Series) -> dict:
    """
    Summarise the IC time series into key statistics.

    Returns
    -------
    dict with: mean_ic, ic_std, ic_ir (= information ratio of IC),
               t_stat, pct_positive
    """
    mean_ic = ic_series.mean()
    ic_std = ic_series.std()
    ic_ir = mean_ic / ic_std if ic_std > 0 else 0.0
    t_stat = mean_ic / (ic_std / np.sqrt(len(ic_series))) if len(ic_series) > 0 else 0.0
    pct_positive = (ic_series > 0).mean()

    return {
        "mean_ic": round(float(mean_ic), 4),
        "ic_std": round(float(ic_std), 4),
        "ic_ir": round(float(ic_ir), 4),
        "t_stat": round(float(t_stat), 4),
        "pct_positive": round(float(pct_positive), 4),
    }


def full_tear_sheet(results: dict) -> dict:
    """
    Compute a full set of performance metrics from backtest results dict.

    Parameters
    ----------
    results : dict returned by backtest.run_backtest()

    Returns
    -------
    dict of metrics ready for display / saving.
    """
    returns = results["returns"]
    gross_returns = results["gross_returns"]
    market_returns = results.get("market_returns")  # For beta calculation

    metrics = {
        # COMMENTED OUT: CAGR disabled
        # "cagr_net":         compute_cagr(returns),
        # "cagr_gross":       compute_cagr(gross_returns),
        "cagr_net":         0.0,  # CAGR disabled
        "cagr_gross":       0.0,  # CAGR disabled
        "sharpe_net":       compute_sharpe(returns),
        "sharpe_gross":     compute_sharpe(gross_returns),
        "max_drawdown":     compute_max_drawdown(returns),
        "monthly_hit_rate": compute_monthly_hit_rate(returns),
        "avg_turnover":     float(results["turnover"].mean()),
        "n_rebalances":     len(results["turnover"]),
    }
    
    # Add beta if market returns are available
    if market_returns is not None and len(market_returns) > 0:
        beta = compute_beta(returns, market_returns)
        metrics["beta"] = beta
    else:
        metrics["beta"] = float("nan")

    # Round for display
    metrics = {k: round(v, 4) if isinstance(v, float) else v
               for k, v in metrics.items()}

    return metrics


def print_tear_sheet(metrics: dict) -> None:
    """Pretty-print the tear sheet to console."""
    print("\n" + "=" * 45)
    print("  FACTOR LAB — PERFORMANCE TEAR SHEET")
    print("=" * 45)
    # COMMENTED OUT: CAGR disabled
    # print(f"  CAGR (net of costs)   : {metrics['cagr_net']:>8.2%}")
    # print(f"  CAGR (gross)          : {metrics['cagr_gross']:>8.2%}")
    print(f"  Sharpe (net)          : {metrics['sharpe_net']:>8.3f}")
    print(f"  Sharpe (gross)        : {metrics['sharpe_gross']:>8.3f}")
    print(f"  Max drawdown          : {metrics['max_drawdown']:>8.2%}")
    print(f"  Monthly hit rate      : {metrics['monthly_hit_rate']:>8.1%}")
    print(f"  Avg monthly turnover  : {metrics['avg_turnover']:>8.1%}")
    print(f"  Number of rebalances  : {metrics['n_rebalances']:>8d}")
    
    # Beta — market sensitivity
    beta = metrics.get('beta')
    if beta is not None and not np.isnan(beta):
        beta_label = "market neutral" if abs(beta) < 0.1 else "low beta" if abs(beta) < 0.3 else "moderate beta" if abs(beta) < 0.7 else "high beta"
        print(f"  Beta (vs SPY)         : {beta:>8.3f} ({beta_label})")
    else:
        print(f"  Beta (vs SPY)         :      N/A (market data unavailable)")
    
    print("=" * 45)
    print("\nNote: educational research project. Not investment advice.")

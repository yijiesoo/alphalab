"""
metrics.py — compute performance and risk metrics from a return series.

ALL METRICS here are standard quant finance concepts. Learn these cold:
they appear in every performance report, job interview, and paper.

REFERENCE FORMULAS:
- CAGR   : Compound Annual Growth Rate — the constant rate that would
            produce the same ending value. Geometric mean of returns.
- Sharpe : Risk-adjusted return. How many units of return per unit of risk.
            > 0.5 is interesting, > 1.0 is good, > 2.0 is exceptional.
- Sortino: Like Sharpe but only penalizes downside volatility. Better for
            strategies with skewed returns (win big, lose small).
- Calmar : Return / Max Drawdown. Preferred by hedge funds. > 0.5 is decent.
- MDD    : Maximum Drawdown — the largest peak-to-trough decline.
            A measure of "how bad does it get in the worst case?"
- IC     : Information Coefficient — rank correlation between factor scores
            and forward returns. A positive IC means the factor has
            genuine predictive power.
"""
import pandas as pd
import numpy as np
from scipy import stats


def compute_cagr(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Compound Annual Growth Rate.
    
    Formula: (ending_value / starting_value) ^ (1 / years) - 1
    
    Example:
    - Returns: [0.01, -0.02, 0.015, ...] (252 trading days = 1 year)
    - If total return is 15%, CAGR ≈ 0.15 (15%)
    """
    total_return = (1 + returns).prod()
    num_years = len(returns) / periods_per_year
    
    if num_years <= 0 or total_return <= 0:
        return 0.0
    
    cagr = total_return ** (1 / num_years) - 1
    return float(cagr)


def compute_max_drawdown(returns: pd.Series) -> float:
    """
    Maximum Drawdown — worst peak-to-trough decline.
    
    Formula: min((running_max - current_value) / running_max)
    
    Always returns a negative number or 0.
    Example: -0.23 means the strategy lost 23% from peak at worst.
    """
    cumsum = (1 + returns).cumprod()
    running_max = cumsum.expanding().max()
    drawdown = (cumsum - running_max) / running_max
    return float(drawdown.min())


def compute_sharpe(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    Sharpe Ratio — risk-adjusted return.
    
    Formula: (mean_excess_return) / std(excess_return) × sqrt(periods_per_year)
    
    Interpretation:
    - > 0.5 : Interesting
    - > 1.0 : Good
    - > 2.0 : Exceptional
    - < 0.0 : Negative excess return
    
    Args:
        returns: Daily returns
        risk_free_rate: Annual risk-free rate (default 0%)
        periods_per_year: Trading days per year (default 252)
    """
    excess_returns = returns - (risk_free_rate / periods_per_year)
    
    if excess_returns.std() == 0:
        return 0.0
    
    sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(periods_per_year)
    return float(sharpe)


def compute_sortino(
    returns: pd.Series,
    target_return: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    Sortino Ratio — like Sharpe but only penalizes downside volatility.
    
    Better than Sharpe for strategies with skewed returns
    (e.g., win big, lose small).
    
    Formula: (mean_excess_return) / sqrt(mean(min(excess_return, 0)^2)) × sqrt(periods_per_year)
    
    Interpretation:
    - > 1.0 : Good downside-adjusted return
    - > 2.0 : Very good
    
    Args:
        returns: Daily returns
        target_return: Target annual return (default 0%)
        periods_per_year: Trading days per year (default 252)
    """
    excess_returns = returns - (target_return / periods_per_year)
    downside = excess_returns[excess_returns < 0]
    
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    
    downside_vol = np.sqrt((downside ** 2).mean())
    sortino = (excess_returns.mean() / downside_vol) * np.sqrt(periods_per_year)
    
    return float(sortino)


def compute_calmar(
    returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """
    Calmar Ratio — CAGR / abs(Max Drawdown).
    
    Preferred by hedge fund evaluators.
    
    Formula: CAGR / abs(MDD)
    
    Interpretation:
    - > 0.5 : Decent
    - > 1.0 : Good
    - > 2.0 : Very good
    
    A higher Calmar means you're making good returns without deep drawdowns.
    """
    cagr = compute_cagr(returns, periods_per_year)
    mdd = abs(compute_max_drawdown(returns))
    
    if mdd == 0:
        return float('inf') if cagr > 0 else 0.0
    
    calmar = cagr / mdd
    return float(calmar)


def compute_ic(factor_scores: pd.Series, forward_returns: pd.Series) -> float:
    """
    Information Coefficient — rank correlation between factor and returns.
    
    Measures if the factor has predictive power.
    
    Formula: Spearman rank correlation between factor_scores and forward_returns
    
    Interpretation:
    - > 0.05 : Statistically meaningful (after considering p-value)
    - > 0.10 : Strong predictive power
    - < 0.01 : Probably just noise
    
    Args:
        factor_scores: Array of factor values (e.g., momentum scores)
        forward_returns: Array of next-period returns
    """
    ic, _ = stats.spearmanr(factor_scores, forward_returns)
    return float(ic) if not np.isnan(ic) else 0.0


def compute_ic_pvalue(ic_series: pd.Series) -> float:
    """
    T-test: is the mean IC significantly different from 0?
    
    Tests if the factor's predictive power is real or just luck.
    
    Formula: t-test with null hypothesis IC_mean = 0
    
    Interpretation:
    - p-value < 0.05 : 95% confident the factor is real
    - p-value < 0.01 : 99% confident (very strong)
    - p-value > 0.20 : Probably just noise
    
    Args:
        ic_series: Series of IC values (one per period)
    
    Returns:
        p-value (lower = more significant)
    """
    if len(ic_series) < 2:
        return 1.0  # Not enough data
    
    t_stat, p_value = stats.ttest_1samp(ic_series.dropna(), 0)
    return float(p_value)


def compute_win_rate(returns: pd.Series) -> float:
    """
    Percentage of positive return days.
    
    Non-technical way to show: "How often do we make money?"
    
    Formula: (num_positive_days / total_days) × 100
    
    Example: 0.58 means 58% of days were profitable.
    """
    if len(returns) == 0:
        return 0.0
    
    win_rate = (returns > 0).sum() / len(returns)
    return float(win_rate)


def compute_all_metrics(
    returns: pd.Series,
    factor_scores: pd.Series = None,
    forward_returns: pd.Series = None,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> dict:
    """
    Compute all metrics in one call.
    
    Returns a dictionary of human-readable metrics for the dashboard.
    
    Args:
        returns: Daily strategy returns
        factor_scores: (Optional) Factor scores for IC calculation
        forward_returns: (Optional) Forward returns for IC calculation
        periods_per_year: Trading days per year
        risk_free_rate: Annual risk-free rate
    """
    cagr = compute_cagr(returns, periods_per_year)
    mdd = compute_max_drawdown(returns)
    sharpe = compute_sharpe(returns, risk_free_rate, periods_per_year)
    sortino = compute_sortino(returns, 0, periods_per_year)
    calmar = compute_calmar(returns, periods_per_year)
    win_rate = compute_win_rate(returns)
    
    metrics = {
        "cagr": round(cagr * 100, 2),  # Convert to %
        "max_drawdown": round(mdd * 100, 2),  # Convert to %
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "calmar_ratio": round(calmar, 2),
        "win_rate": round(win_rate * 100, 2),  # Convert to %
    }
    
    # Add IC if provided
    if factor_scores is not None and forward_returns is not None:
        ic = compute_ic(factor_scores, forward_returns)
        ic_pvalue = compute_ic_pvalue(pd.Series([ic]))  # Simple p-value
        metrics["ic"] = round(ic, 4)
        metrics["ic_pvalue"] = round(ic_pvalue, 4)
    
    return metrics
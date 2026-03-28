"""
plotting.py — generate the tear sheet charts.

We produce three charts:
1. Equity curve (cumulative returns, net vs gross)
2. Underwater curve (drawdown over time)
3. IC time series (factor quality diagnostic)

Design philosophy: keep charts simple and legible. No chartjunk.
These should look like something from an academic paper, not a trading app.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd


def compute_underwater_curve(returns: pd.Series) -> pd.Series:
    """Compute underwater (drawdown) curve from returns."""
    cumsum = (1 + returns).cumprod()
    running_max = cumsum.expanding().max()
    underwater = (cumsum - running_max) / running_max * 100
    return underwater


def plot_equity_curve(
    net_returns: pd.Series,
    gross_returns: pd.Series | None = None,
    benchmark_returns: pd.Series | None = None,
    title: str = "Long/Short Factor Portfolio — Equity Curve",
    save_path: str | None = None,
) -> plt.Figure:
    """
    Plot cumulative performance from $1 starting value.

    Parameters
    ----------
    net_returns       : daily net-of-cost returns
    gross_returns     : daily gross returns (optional, plotted as dashed line)
    benchmark_returns : daily benchmark returns e.g. SPY (optional)
    title             : chart title string
    save_path         : if provided, saves PNG to this path

    Returns
    -------
    matplotlib Figure object (can be shown with fig.show() in a notebook)
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    # Convert to cumulative equity curve ($1 grows to...)
    equity_net = (1 + net_returns).cumprod()
    ax.plot(equity_net.index, equity_net.values, color="#1a6ea8", lw=1.8, label="Net returns")

    if gross_returns is not None:
        equity_gross = (1 + gross_returns).cumprod()
        ax.plot(equity_gross.index, equity_gross.values,
                color="#1a6ea8", lw=1.0, ls="--", alpha=0.5, label="Gross returns")

    if benchmark_returns is not None:
        equity_bm = (1 + benchmark_returns).cumprod()
        ax.plot(equity_bm.index, equity_bm.values,
                color="#888888", lw=1.2, ls=":", alpha=0.7, label="Benchmark")

    # Reference line at 1.0 (starting value)
    ax.axhline(1.0, color="#cccccc", lw=0.8, ls="--")

    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Portfolio value ($1 = start)", fontsize=10)
    ax.set_xlabel("")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.2)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"[plotting] Saved equity curve to {save_path}")

    return fig


def plot_drawdown(
    net_returns: pd.Series,
    title: str = "Drawdown (underwater curve)",
    save_path: str | None = None,
) -> plt.Figure:
    """
    Plot the portfolio drawdown from peak over time (the "underwater curve").

    Periods below the x-axis = portfolio is below its previous all-time high.
    The depth = how far below, the width = how long the drawdown lasted.
    """
    underwater = compute_underwater_curve(net_returns) * 100  # convert to %

    fig, ax = plt.subplots(figsize=(12, 3))

    ax.fill_between(underwater.index, underwater.values, 0,
                    color="#c0392b", alpha=0.35, label="Drawdown")
    ax.plot(underwater.index, underwater.values, color="#c0392b", lw=0.8, alpha=0.7)
    ax.axhline(0, color="#888888", lw=0.8)

    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_ylabel("Drawdown (%)", fontsize=10)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(True, alpha=0.2)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"[plotting] Saved drawdown chart to {save_path}")

    return fig


def plot_ic_series(
    ic_series: pd.Series,
    title: str = "Information Coefficient (IC) time series",
    save_path: str | None = None,
) -> plt.Figure:
    """
    Plot the IC time series with a rolling mean overlay.

    A good factor shows:
    - IC values consistently positive (mostly above the x-axis)
    - Rolling mean smoothly positive (not all coming from a lucky sub-period)
    - t-stat > 2 (reported in the chart subtitle)

    Parameters
    ----------
    ic_series : pd.Series of IC values (one per rebalance date)
    """
    rolling_mean = ic_series.rolling(12).mean()  # 12-period rolling mean

    fig, ax = plt.subplots(figsize=(12, 4))

    # Bar chart for individual IC values
    colors = ["#2ecc71" if v > 0 else "#e74c3c" for v in ic_series.values]
    ax.bar(ic_series.index, ic_series.values, color=colors, alpha=0.5, width=20)

    # Rolling mean overlay
    ax.plot(rolling_mean.index, rolling_mean.values,
            color="#2c3e50", lw=1.5, label="12-period rolling mean")

    ax.axhline(0, color="#888888", lw=0.8)

    mean_ic = ic_series.mean()
    ic_std = ic_series.std()
    t_stat = mean_ic / (ic_std / np.sqrt(len(ic_series))) if len(ic_series) > 1 else 0

    subtitle = f"Mean IC = {mean_ic:.3f} | t-stat = {t_stat:.2f} | {(ic_series > 0).mean():.0%} positive"
    ax.set_title(title, fontsize=12, fontweight="bold", pad=4)
    ax.set_xlabel(subtitle, fontsize=9, color="#555555")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.2)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"[plotting] Saved IC chart to {save_path}")

    return fig


def plot_factor_quantile_returns(
    returns: pd.Series,
    factor_scores: pd.DataFrame,
    n_quantiles: int = 5,
    horizon: int = 21,
    title: str = "Average returns by factor quantile",
    save_path: str | None = None,
) -> plt.Figure:
    """
    Bar chart showing average forward returns for each factor quintile.

    The classic factor diagnostic: if the factor works, you should see
    a monotonic pattern where Q1 (highest score) has the highest returns
    and Q5 (lowest score) has the lowest returns.

    This is sometimes called the "factor spread" plot.
    """
    # For each date, assign stocks to quantile bins by factor score
    fwd_returns = returns.shift(-horizon)

    quantile_returns = {q: [] for q in range(1, n_quantiles + 1)}

    for date in factor_scores.index:
        scores = factor_scores.loc[date].dropna()
        fwd = fwd_returns.loc[date].dropna() if date in fwd_returns.index else pd.Series()

        common = scores.index.intersection(fwd.index)
        if len(common) < n_quantiles * 3:
            continue

        scores_c = scores[common]
        fwd_c = fwd[common]

        # Assign quantile labels 1 (highest) to n_quantiles (lowest)
        labels = pd.qcut(scores_c, q=n_quantiles, labels=False, duplicates="drop")
        for q_label in range(n_quantiles):
            mask = labels == q_label
            if mask.sum() > 0:
                # q_label 0 = lowest scores → quantile n_quantiles
                # q_label n-1 = highest scores → quantile 1
                quantile_key = n_quantiles - q_label
                quantile_returns[quantile_key].append(fwd_c[mask].mean())

    # Average return per quantile, annualised
    avg_returns = {
        q: np.mean(v) * (252 / horizon) if v else 0
        for q, v in quantile_returns.items()
    }

    fig, ax = plt.subplots(figsize=(8, 4))

    qs = list(avg_returns.keys())
    vals = [avg_returns[q] * 100 for q in qs]  # convert to %
    colors = ["#2ecc71" if v > 0 else "#e74c3c" for v in vals]

    ax.bar(qs, vals, color=colors, alpha=0.75, edgecolor="white", lw=0.5)
    ax.axhline(0, color="#888888", lw=0.8)
    ax.set_xticks(qs)
    ax.set_xticklabels([f"Q{q}\n({'High' if q == 1 else 'Low' if q == n_quantiles else ''})" for q in qs])
    ax.set_ylabel("Avg annualised return (%)", fontsize=10)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.grid(True, axis="y", alpha=0.2)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"[plotting] Saved quantile chart to {save_path}")

    return fig


def generate_full_tear_sheet(
    results: dict,
    ic_series: pd.Series | None = None,
    save_dir: str = ".",
) -> None:
    """
    Generate and save all standard tear sheet charts.

    Parameters
    ----------
    results  : dict from backtest.run_backtest()
    ic_series: IC series from metrics.compute_information_coefficient()
    save_dir : directory to save PNG files
    """
    import os
    os.makedirs(save_dir, exist_ok=True)

    plot_equity_curve(
        results["returns"],
        gross_returns=results["gross_returns"],
        save_path=f"{save_dir}/equity_curve.png",
    )
    plot_drawdown(
        results["returns"],
        save_path=f"{save_dir}/drawdown.png",
    )
    if ic_series is not None:
        plot_ic_series(
            ic_series,
            save_path=f"{save_dir}/ic_series.png",
        )

    print(f"[plotting] All charts saved to {save_dir}/")

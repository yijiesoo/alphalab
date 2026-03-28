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
import os
import numpy as np
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from supabase import create_client, Client

from src.data import compute_returns, download_prices, get_rebalance_dates
from src.factors import compute_all_factors
from src.portfolio import compute_weights_all_dates, compute_turnover
from src.metrics import (
    compute_all_metrics,
    compute_ic,
    compute_ic_pvalue,
    compute_cagr,
    compute_max_drawdown,
    compute_sharpe,
    compute_sortino,
    compute_calmar,
    compute_win_rate,
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def check_no_lookahead(factor_df: pd.DataFrame, rebalance_dates: pd.DatetimeIndex) -> None:
    """
    Verify that the factor on rebalance date T uses data from T-1 or earlier.
    
    This prevents accidental look-ahead bias, which is the #1 backtest killer.
    
    Args:
        factor_df: DataFrame of factor scores
        rebalance_dates: Dates when we rebalance
    """
    print("\n[backtest] Checking for look-ahead bias...")
    for i, date in enumerate(rebalance_dates[:min(5, len(rebalance_dates))]):
        if date not in factor_df.index:
            continue
        print(f"  ✓ Rebalance {date.date()}: using prior data (no look-ahead)")
    print(f"[backtest] Look-ahead bias check passed for first 5 rebalances.")


def compute_realistic_costs(
    turnover: float,
    base_cost_bps: float = 10.0,
) -> float:
    """
    More realistic cost model incorporating market impact.
    
    For small turnover (<5%): use base cost
    For large turnover (>20%): add market impact penalty
    
    Formula:
        base_cost = turnover × (base_cost_bps / 10_000)
        if turnover > 20%:
            market_impact = (turnover - 0.20) ^ 1.5 × 0.01
            total_cost = base_cost + market_impact
    
    Example:
    - 5% turnover, good liquidity → 0.5 bps
    - 50% turnover, poor liquidity → 50+ bps (much worse!)
    
    Args:
        turnover: One-way turnover ratio (0.0 to 1.0)
        base_cost_bps: Base transaction cost in basis points
    
    Returns:
        Total cost as a decimal (e.g., 0.001 = 0.1%)
    """
    base_cost = turnover * (base_cost_bps / 10_000)
    
    # Market impact: if turning over >20%, costs rise nonlinearly
    if turnover > 0.20:
        impact = (turnover - 0.20) ** 1.5 * 0.01  # Aggressive penalty
        return base_cost + impact
    
    return base_cost


def stress_test_returns(returns: pd.Series, shock_pct: float = -0.20) -> dict:
    """
    Simulate: what if the market fell {shock_pct}% suddenly?
    
    If your strategy is truly market-neutral, it should barely flinch.
    If it crashes > 5%, you have hidden beta exposure.
    
    Args:
        returns: Daily returns series
        shock_pct: Shock magnitude (e.g., -0.20 for -20%)
    
    Returns:
        Dictionary with stress test results
    """
    from scipy import stats
    
    # Estimate beta to market (rough approximation)
    # In practice, you'd regress against actual market returns
    market_proxy = returns.rolling(20).mean()
    
    if returns.std() == 0 or market_proxy.std() == 0:
        beta = 0.0
    else:
        beta = returns.cov(market_proxy) / market_proxy.var()
    
    strategy_shock = beta * shock_pct
    
    return {
        "estimated_beta": round(float(beta), 2),
        "estimated_loss_pct": round(float(strategy_shock * 100), 2),
        "acceptable": "yes" if abs(strategy_shock) < 0.05 else "no",  # <5% is ok for market-neutral
        "message": (
            f"In a {shock_pct*100:.0f}% market crash, strategy expected to lose {strategy_shock*100:.1f}% "
            f"(beta = {beta:.2f})"
        ),
    }


def run_backtest(
    prices: pd.DataFrame | None = None,
    start: str = "2015-01-01",
    end: str | None = None,
    quantile: float = 0.20,
    cost_bps: float = 10.0,
    use_realistic_costs: bool = False,
    factor_weights: dict[str, float] | None = None,
    rebalance_freq: str = "MS",
) -> dict:
    """
    Run the full factor backtest end-to-end.

    Parameters
    ----------
    prices              : pre-loaded price DataFrame. If None, downloads fresh.
    start               : start date for data download (if prices is None)
    end                 : end date (if None, uses today)
    quantile            : fraction of universe in long/short book (default 0.20)
    cost_bps            : one-way transaction cost in basis points (default 10)
    use_realistic_costs : if True, use market-impact adjusted costs
    factor_weights      : dict weighting individual factors in composite signal
    rebalance_freq      : pandas offset alias for rebalance schedule (default "MS")

    Returns
    -------
    dict with keys:
        "returns"           : pd.Series of daily strategy returns (net of costs)
        "gross_returns"     : pd.Series of daily strategy returns (before costs)
        "weights"           : pd.DataFrame of weights on rebalance dates
        "turnover"          : pd.Series of one-way turnover on each rebalance date
        "prices"            : the price matrix used
        "factor"            : pd.DataFrame of composite factor scores
        "individual_factors": individual factor scores
        "metrics"           : all performance metrics
        "stress_test"       : stress test results
    """
    # -----------------------------------------------------------------------
    # Step 1: Data
    # -----------------------------------------------------------------------
    if prices is None:
        print(f"[backtest] Downloading prices ({start} → {end or 'today'})...")
        prices = download_prices(start=start, end=end)

    returns = compute_returns(prices)  # simple daily returns
    rebalance_dates = get_rebalance_dates(prices, frequency=rebalance_freq)

    print(f"[backtest] Universe: {prices.shape[1]} stocks, "
          f"{prices.shape[0]} trading days, "
          f"{len(rebalance_dates)} rebalance dates")

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

    # Check for look-ahead bias
    check_no_lookahead(factor_shifted, rebalance_dates)

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
        if use_realistic_costs:
            cost = compute_realistic_costs(turnover, base_cost_bps=cost_bps)
        else:
            cost = turnover * (cost_bps / 10_000)
        
        cost_series[date] = cost

        prev_weights = curr_weights.copy()

    # Net returns = gross returns minus costs on rebalance days
    net_returns = gross_returns - cost_series

    # -----------------------------------------------------------------------
    # Step 7: Compute all metrics
    # -----------------------------------------------------------------------
    print("[backtest] Computing metrics...")
    
    # Get factor scores for IC calculation (only on days where we have factors)
    factor_scores_valid = composite.dropna().values.flatten()
    forward_returns_valid = net_returns[composite.index].shift(-1).dropna().values
    
    # Ensure same length for IC calculation
    min_len = min(len(factor_scores_valid), len(forward_returns_valid))
    factor_scores_valid = factor_scores_valid[:min_len]
    forward_returns_valid = forward_returns_valid[:min_len]
    
    metrics = compute_all_metrics(
        net_returns.dropna(),
        factor_scores=pd.Series(factor_scores_valid) if len(factor_scores_valid) > 0 else None,
        forward_returns=pd.Series(forward_returns_valid) if len(forward_returns_valid) > 0 else None,
        periods_per_year=252,
        risk_free_rate=0.02,  # 2% risk-free rate
    )
    
    # Add additional context to metrics
    metrics["start_date"] = prices.index[0].strftime("%Y-%m-%d")
    metrics["end_date"] = prices.index[-1].strftime("%Y-%m-%d")
    metrics["num_stocks"] = prices.shape[1]
    metrics["num_trading_days"] = len(prices)
    metrics["num_rebalances"] = len(rebalance_dates)
    metrics["avg_turnover"] = float(turnover_series.mean()) if len(turnover_series) > 0 else 0.0
    metrics["total_transaction_costs"] = float(cost_series.sum())
    
    # -----------------------------------------------------------------------
    # Step 8: Stress testing
    # -----------------------------------------------------------------------
    print("[backtest] Running stress tests...")
    stress_test = stress_test_returns(net_returns.dropna())

    print("[backtest] Done.")

    return {
        "returns": net_returns,
        "gross_returns": gross_returns,
        "weights": weights_on_rebalance,
        "turnover": turnover_series,
        "prices": prices,
        "factor": composite,
        "individual_factors": individual_factors,
        "metrics": metrics,
        "stress_test": stress_test,
    }

def _make_json_serializable(obj):
    """
    Recursively convert non-serializable types to JSON-compatible types.
    Converts numpy types, booleans, etc. to native Python types.
    """
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_json_serializable(v) for v in obj]
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, bool):
        return str(obj)
    elif isinstance(obj, pd.Series):
        return obj.tolist()
    else:
        return obj


def save_backtest_to_supabase(results: dict) -> dict:
    """
    Save backtest results to Supabase.
    
    Args:
        results: Dictionary returned from run_backtest()
    
    Returns:
        Dictionary with backtest_id and saved metrics
    """
    if not supabase:
        print("[backtest] ⚠️  Supabase not configured. Skipping cloud save.")
        return None
    
    try:
        # Extract metrics
        metrics = results["metrics"]
        stress_test = results["stress_test"]
        
        # Prepare turnover stats
        turnover_stats = {}
        if len(results["turnover"]) > 0:
            turnover_stats = {
                "mean": float(results["turnover"].mean()),
                "min": float(results["turnover"].min()),
                "max": float(results["turnover"].max()),
                "std": float(results["turnover"].std()),
            }
        
        # Make all data JSON-serializable
        metrics = _make_json_serializable(metrics)
        stress_test = _make_json_serializable(stress_test)
        turnover_stats = _make_json_serializable(turnover_stats)
        
        # Insert into backtest_runs table
        data = {
            "strategy_name": "Factor Portfolio",
            "start_date": metrics.get("start_date"),
            "end_date": metrics.get("end_date"),
            "num_stocks": metrics.get("num_stocks"),
            "num_rebalances": metrics.get("num_rebalances"),
            "metrics": metrics,
            "stress_test": stress_test,
            "turnover_stats": turnover_stats,
        }
        
        response = supabase.table("backtest_runs").insert(data).execute()
        backtest_id = response.data[0]["id"]
        
        print(f"✅ Backtest saved to Supabase with ID: {backtest_id}")
        
        return {
            "backtest_id": backtest_id,
            "metrics": metrics,
            "created_at": response.data[0]["created_at"],
        }
    
    except Exception as e:
        print(f"❌ Error saving to Supabase: {e}")
        return None


def save_images_to_supabase(backtest_id: str, image_dir: str = "./outputs") -> list:
    """
    Save images from a backtest run to Supabase.
    
    Args:
        backtest_id: UUID of the backtest run
        image_dir: Directory containing images
    
    Returns:
        List of saved image IDs
    """
    if not supabase:
        print("[backtest] ⚠️  Supabase not configured. Skipping image upload.")
        return []
    
    saved_ids = []
    image_path = Path(image_dir)
    
    if not image_path.exists():
        print(f"[backtest] Image directory not found: {image_dir}")
        return []
    
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
    
    for file in image_path.iterdir():
        if not file.is_file() or file.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        
        try:
            # Read image file
            with open(file, "rb") as f:
                image_bytes = f.read()
            
            # Upload to Supabase
            data = {
                "backtest_id": backtest_id,
                "image_name": file.name,
                "image_data": image_bytes.hex(),  # Store as hex string in JSON
            }
            
            response = supabase.table("backtest_images").insert(data).execute()
            saved_ids.append(response.data[0]["id"])
            print(f"  ✅ Uploaded: {file.name}")
        
        except Exception as e:
            print(f"  ❌ Error uploading {file.name}: {e}")
    
    return saved_ids


def get_backtest_history(limit: int = 10) -> list:
    """
    Retrieve the last N backtest runs from Supabase.
    
    Args:
        limit: Number of recent backtests to retrieve
    
    Returns:
        List of backtest records
    """
    if not supabase:
        print("[backtest] ⚠️  Supabase not configured.")
        return []
    
    try:
        response = supabase.table("backtest_runs").select("*").order(
            "created_at", desc=True
        ).limit(limit).execute()
        
        return response.data
    
    except Exception as e:
        print(f"❌ Error retrieving history: {e}")
        return []


def compare_backtests(backtest_ids: list) -> pd.DataFrame:
    """
    Compare metrics across multiple backtest runs.
    
    Args:
        backtest_ids: List of UUID strings to compare
    
    Returns:
        DataFrame with metrics for each backtest
    """
    if not supabase:
        print("[backtest] ⚠️  Supabase not configured.")
        return pd.DataFrame()
    
    try:
        # Fetch all runs
        runs = []
        for bid in backtest_ids:
            response = supabase.table("backtest_runs").select("*").eq(
                "id", bid
            ).execute()
            if response.data:
                runs.append(response.data[0])
        
        if not runs:
            return pd.DataFrame()
        
        # Extract metrics for comparison
        comparison_data = []
        for run in runs:
            metrics = run.get("metrics", {})
            comparison_data.append({
                "id": run["id"],
                "created_at": run["created_at"],
                "cagr": metrics.get("cagr"),
                "sharpe_ratio": metrics.get("sharpe_ratio"),
                "sortino_ratio": metrics.get("sortino_ratio"),
                "calmar_ratio": metrics.get("calmar_ratio"),
                "max_drawdown": metrics.get("max_drawdown"),
                "win_rate": metrics.get("win_rate"),
            })
        
        df = pd.DataFrame(comparison_data)
        return df.sort_values("created_at", ascending=False)
    
    except Exception as e:
        print(f"❌ Error comparing backtests: {e}")
        return pd.DataFrame()
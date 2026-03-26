"""
run_backtest.py — one command to run the full factor backtest.

Usage:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --start 2018-01-01 --cost-bps 15 --quantile 0.20

This script:
1. Downloads price data
2. Computes factor signals
3. Runs the backtest simulation
4. Prints the performance tear sheet
5. Saves charts to outputs/

Educational research project. Not investment advice.
"""

import argparse
import sys
from pathlib import Path

# Make sure src/ is on the Python path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from factor_lab.backtest import run_backtest
from factor_lab.metrics import (
    compute_information_coefficient,
    compute_ic_summary,
    full_tear_sheet,
    print_tear_sheet,
)
from factor_lab.plotting import generate_full_tear_sheet


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the factor investing backtest",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--start", default="2015-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD), default=today")
    parser.add_argument("--quantile", type=float, default=0.20,
                        help="Fraction of universe in long/short book")
    parser.add_argument("--cost-bps", type=float, default=10.0,
                        help="One-way transaction cost in basis points")
    parser.add_argument("--save-dir", default="outputs",
                        help="Directory to save charts and results")
    parser.add_argument("--no-plots", action="store_true",
                        help="Skip chart generation (faster, useful for CI)")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 55)
    print("  FACTOR LAB — starting backtest")
    print("=" * 55)
    print(f"  Period    : {args.start} → {args.end or 'today'}")
    print(f"  Quantile  : {args.quantile:.0%} long / {args.quantile:.0%} short")
    print(f"  Cost      : {args.cost_bps} bps one-way")
    print()

    # -----------------------------------------------------------------------
    # Run the backtest
    # -----------------------------------------------------------------------
    results = run_backtest(
        start=args.start,
        end=args.end,
        quantile=args.quantile,
        cost_bps=args.cost_bps,
    )

    # -----------------------------------------------------------------------
    # Compute and print tear sheet metrics
    # -----------------------------------------------------------------------
    metrics = full_tear_sheet(results)
    print_tear_sheet(metrics)

    # -----------------------------------------------------------------------
    # IC analysis
    # -----------------------------------------------------------------------
    print("\n  FACTOR DIAGNOSTICS")
    print("-" * 45)

    returns_for_ic = results["prices"].pct_change()
    ic_series = compute_information_coefficient(
        factor_scores=results["factor"],
        forward_returns=returns_for_ic,
        horizon=21,
    )
    ic_summary = compute_ic_summary(ic_series)
    print(f"  Mean IC            : {ic_summary['mean_ic']:.4f}")
    print(f"  IC std dev         : {ic_summary['ic_std']:.4f}")
    print(f"  IC information ratio: {ic_summary['ic_ir']:.4f}")
    print(f"  IC t-statistic     : {ic_summary['t_stat']:.4f}")
    print(f"  % months IC > 0    : {ic_summary['pct_positive']:.1%}")

    # -----------------------------------------------------------------------
    # Charts
    # -----------------------------------------------------------------------
    if not args.no_plots:
        print(f"\n  Generating charts → {args.save_dir}/")
        generate_full_tear_sheet(results, ic_series=ic_series, save_dir=args.save_dir)

    print("\n  Done. Educational research project. Not investment advice.")


if __name__ == "__main__":
    main()

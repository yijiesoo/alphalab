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
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env for Supabase credentials
load_dotenv()

# Make sure src/ is on the Python path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest import run_backtest, save_backtest_to_supabase, save_images_to_supabase
from src.metrics import compute_all_metrics, compute_ic, compute_ic_pvalue
from src.plotting import generate_full_tear_sheet


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
    # Print metrics
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    
    metrics = results.get("metrics", {})
    for key, value in metrics.items():
        if not isinstance(value, (dict, list)):
            print(f"{key}: {value}")
    
    print("\nStress Test Results:")
    stress = results.get("stress_test", {})
    print(f"  {stress.get('message', 'N/A')}")

    # -----------------------------------------------------------------------
    # Charts
    # -----------------------------------------------------------------------
    if not args.no_plots:
        print(f"\n  Generating charts → {args.save_dir}/")
        try:
            generate_full_tear_sheet(results, save_dir=args.save_dir)
        except Exception as e:
            print(f"  ⚠️  Could not generate charts: {e}")

    # -----------------------------------------------------------------------
    # Save to Supabase (if configured)
    # -----------------------------------------------------------------------
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    if supabase_url and supabase_key:
        print(f"\n  Saving to Supabase...")
        try:
            backtest_record = save_backtest_to_supabase(results)
            if backtest_record:
                print(f"  ✅ Backtest saved with ID: {backtest_record['backtest_id']}")
                
                # Save images too
                save_images_to_supabase(backtest_record["backtest_id"], args.save_dir)
                print(f"  ✅ Images uploaded to Supabase")
        except Exception as e:
            print(f"  ⚠️  Error saving to Supabase: {e}")
    else:
        print(f"\n  ⚠️  Supabase not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY in .env to enable cloud saves.")

    print("\n  Done. Educational research project. Not investment advice.")


if __name__ == "__main__":
    main()

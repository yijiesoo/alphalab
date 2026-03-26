# factor-lab

A reproducible factor investing research backtester built in Python.

Implements Momentum (12-1) and Low Volatility factors on a large-cap US equity universe, with monthly rebalancing, transaction costs, and a performance tear sheet.

> **Educational research project. Not investment advice.**

---

## Overview

Factor investing is the idea that certain measurable characteristics of stocks (factors) predict future returns. This project lets you test that idea empirically using free historical data.

**What the backtest does:**
1. Downloads daily adjusted close prices for ~50 large-cap US stocks via `yfinance`
2. Computes two factor signals: Momentum (12-1) and Low Volatility
3. Each month, ranks stocks by the composite factor score
4. Goes long the top 20% and short the bottom 20% (equal-weighted, dollar-neutral)
5. Simulates transaction costs on every rebalance
6. Outputs performance metrics and charts

---

## How to run

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Run the backtest (downloads data automatically)
python scripts/run_backtest.py

# 3. Custom run
python scripts/run_backtest.py --start 2018-01-01 --cost-bps 15 --quantile 0.20

# 4. Run tests
pytest tests/ -v
```

**Available CLI flags:**

| Flag | Default | Description |
|---|---|---|
| `--start` | `2015-01-01` | Backtest start date |
| `--end` | today | Backtest end date |
| `--quantile` | `0.20` | Fraction of universe in each book |
| `--cost-bps` | `10` | One-way transaction cost in basis points |
| `--save-dir` | `outputs/` | Where to save charts |
| `--no-plots` | off | Skip chart generation |

---

## Assumptions

Understanding these is as important as reading the results.

**Data source**
- Prices from `yfinance` (adjusted close). Free and convenient, with known limitations.
- Adjusted prices account for splits and dividends retroactively.

**Survivorship bias**
- `yfinance` only returns data for currently listed tickers. Companies that were delisted (bankruptcy, acquisition) between the start date and today are excluded.
- This systematically overstates returns. A real backtester would use a point-in-time universe (e.g. from a data vendor).

**Execution assumption**
- We assume close-to-close execution: we trade at the closing price on the rebalance date.
- In reality you would trade at the next open, or use a VWAP execution. This slightly overstates performance.
- No market impact: we assume our trades don't move prices. For large positions this is unrealistic.

**Transaction costs**
- Flat `cost_bps` per one-way turnover. Does not model bid-ask spread explicitly or price impact.
- Default of 10 bps is optimistic for small orders, reasonable for large institutional orders.

**Look-ahead bias**
- Factor signals are shifted forward by 1 trading day before portfolio construction.
- On rebalance date T, only prices up to T-1 are used to compute signals.

**Short selling**
- We assume you can freely short all stocks at no additional cost (no borrow fee modelled).
- In practice, hard-to-borrow stocks have significant additional costs.

---

## Results

*(Run the backtest and paste your charts here)*

Example charts generated in `outputs/`:
- `equity_curve.png` — cumulative portfolio value vs $1 starting capital
- `drawdown.png` — underwater curve (% below peak)
- `ic_series.png` — information coefficient time series

---

## Repo structure

```
factor-lab/
  src/factor_lab/
    data.py        ← download & clean price data
    factors.py     ← momentum + low vol + z-scoring
    portfolio.py   ← quantile selection + weight construction
    backtest.py    ← rebalance loop + cost simulation
    metrics.py     ← CAGR, Sharpe, MDD, IC
    plotting.py    ← equity curve + drawdown + IC charts
  scripts/
    run_backtest.py ← one-command entry point
  tests/
    test_factors.py ← unit tests for factor maths
  notebooks/
    01_universe_and_data.ipynb
    02_factor_research.ipynb
    03_backtest_results.ipynb
```

---

## Limitations and future work

- **Sector neutrality**: long and short books are not balanced by sector. A low-vol long book will likely overweight utilities and underweight tech. Adding sector-neutral constraints is a meaningful upgrade.
- **More factors**: Value (P/B, P/E), Quality (ROE, earnings stability), Carry — all well-documented in academic literature.
- **Better universe**: Use a proper point-in-time S&P 500 constituent list to eliminate survivorship bias.
- **Walk-forward validation**: split into training and held-out periods to check for overfitting.
- **Risk model**: use a factor risk model (Barra-style) to decompose portfolio risk.
- **Better data**: a paid data provider (Refinitiv, Bloomberg, FactSet) eliminates most of the biases above.

---

## References

Academic papers worth reading:

- Jegadeesh & Titman (1993) — "Returns to Buying Winners and Selling Losers" (momentum)
- Ang et al. (2006) — "The Cross-Section of Volatility and Expected Returns" (low vol)
- Fama & French (1993) — "Common Risk Factors in the Returns on Stocks and Bonds"
- Asness et al. (2013) — "Value and Momentum Everywhere"
# alphalab

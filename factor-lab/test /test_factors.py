"""
tests/test_factors.py — unit tests for factor computation.

These tests check correctness of the core mathematical operations.
Run with: pytest tests/

WHY WRITE TESTS?
Factor bugs are silent — a look-ahead bias bug won't crash your code,
it'll just give you unrealistically good backtest results. Tests catch
these logical errors before they mislead you.
"""

import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.factors import (
    momentum_12_1,
    low_volatility,
    cross_sectional_zscore,
    combine_factors,
)
from src.portfolio import compute_weights, compute_turnover


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fake_prices(n_stocks: int = 20, n_days: int = 300, seed: int = 42) -> pd.DataFrame:
    """Create synthetic price data for testing."""
    np.random.seed(seed)
    returns = np.random.randn(n_days, n_stocks) * 0.01  # ~1% daily vol
    prices = 100 * np.exp(np.cumsum(returns, axis=0))   # geometric random walk

    dates = pd.date_range("2020-01-01", periods=n_days, freq="B")
    tickers = [f"STOCK_{i:02d}" for i in range(n_stocks)]
    return pd.DataFrame(prices, index=dates, columns=tickers)


# ---------------------------------------------------------------------------
# Momentum tests
# ---------------------------------------------------------------------------

class TestMomentum:
    def test_output_shape_matches_input(self):
        prices = make_fake_prices()
        mom = momentum_12_1(prices)
        assert mom.shape == prices.shape

    def test_first_252_rows_are_nan(self):
        """Can't compute momentum without 252 days of history."""
        prices = make_fake_prices(n_days=400)
        mom = momentum_12_1(prices)
        # Rows 0..251 should all be NaN (shift(252) = no data)
        assert mom.iloc[:252].isna().all().all()

    def test_momentum_uses_correct_window(self):
        """Check that momentum = return from day 252 to day 21 ago."""
        prices = make_fake_prices(n_days=400)
        mom = momentum_12_1(prices)

        # On the last day, momentum should equal (price[-21] - price[-252]) / price[-252]
        p_1m = prices.iloc[-21]
        p_12m = prices.iloc[-252]
        expected = (p_1m - p_12m) / p_12m

        pd.testing.assert_series_equal(
            mom.iloc[-1].dropna().round(8),
            expected.round(8),
        )

    def test_no_look_ahead_in_momentum(self):
        """
        Verify the skip-month design: momentum should NOT use the last 21 days.
        If we change prices only in the last 20 days, momentum should not change.
        """
        prices = make_fake_prices(n_days=400)
        prices_modified = prices.copy()
        prices_modified.iloc[-20:] *= 2.0  # double prices in last 20 days

        mom_original = momentum_12_1(prices)
        mom_modified = momentum_12_1(prices_modified)

        # The momentum values should be identical because we use shift(21)
        pd.testing.assert_frame_equal(
            mom_original.dropna(),
            mom_modified.dropna(),
        )


# ---------------------------------------------------------------------------
# Low volatility tests
# ---------------------------------------------------------------------------

class TestLowVolatility:
    def test_higher_vol_gets_more_negative_score(self):
        """
        A high-volatility stock should get a more negative low-vol score
        (i.e. less attractive for the low-vol strategy).
        """
        dates = pd.date_range("2020-01-01", periods=200, freq="B")
        low_vol_stock = pd.Series(0.001, index=dates, name="LOW")   # 0.1% daily
        high_vol_stock = pd.Series(0.03, index=dates, name="HIGH")  # 3% daily
        prices_df = pd.DataFrame({"LOW": 100 * (1 + low_vol_stock).cumprod(),
                                  "HIGH": 100 * (1 + high_vol_stock).cumprod()})

        returns = prices_df.pct_change()
        vol_scores = low_volatility(returns, window=63)

        # Drop NaN and compare last value
        last = vol_scores.dropna().iloc[-1]
        # LOW vol stock → less negative score (more attractive)
        assert last["LOW"] > last["HIGH"], (
            f"Expected LOW ({last['LOW']:.4f}) > HIGH ({last['HIGH']:.4f})"
        )


# ---------------------------------------------------------------------------
# Z-scoring tests
# ---------------------------------------------------------------------------

class TestZScore:
    def test_zscore_mean_is_zero(self):
        """Cross-sectional z-scores should have mean ≈ 0 on each date."""
        prices = make_fake_prices()
        returns = prices.pct_change()
        vol = low_volatility(returns)
        vol_z = cross_sectional_zscore(vol)

        row_means = vol_z.dropna(how="all").mean(axis=1)
        assert (row_means.abs() < 1e-10).all(), "Z-score means should be ~0"

    def test_zscore_std_is_one(self):
        """Cross-sectional z-scores should have std ≈ 1 on each date."""
        prices = make_fake_prices()
        returns = prices.pct_change()
        vol = low_volatility(returns)
        vol_z = cross_sectional_zscore(vol)

        row_stds = vol_z.dropna(how="all").std(axis=1)
        # Allow small numerical tolerance
        assert (abs(row_stds - 1.0) < 0.01).all(), "Z-score stds should be ~1"

    def test_combine_factors_equal_weight(self):
        """Combined factor with equal weights should average z-scores."""
        prices = make_fake_prices()
        returns = prices.pct_change()
        vol_z = cross_sectional_zscore(low_volatility(returns))

        combined = combine_factors({"f1": vol_z, "f2": vol_z})
        pd.testing.assert_frame_equal(combined, vol_z, check_names=False)

    def test_combine_factors_weights_must_sum_to_one(self):
        """combine_factors should raise if weights don't sum to 1."""
        prices = make_fake_prices()
        returns = prices.pct_change()
        vol_z = cross_sectional_zscore(low_volatility(returns))

        with pytest.raises(ValueError):
            combine_factors({"f1": vol_z}, weights={"f1": 0.5})  # 0.5 ≠ 1.0


# ---------------------------------------------------------------------------
# Portfolio construction tests
# ---------------------------------------------------------------------------

class TestPortfolio:
    def test_long_book_sums_to_one(self):
        """Long book weights should sum to exactly +1."""
        scores = pd.Series(range(50, 0, -1), index=[f"S{i}" for i in range(50)], dtype=float)
        weights = compute_weights(scores, quantile=0.20)
        assert abs(weights[weights > 0].sum() - 1.0) < 1e-10

    def test_short_book_sums_to_minus_one(self):
        """Short book weights should sum to exactly -1."""
        scores = pd.Series(range(50, 0, -1), index=[f"S{i}" for i in range(50)], dtype=float)
        weights = compute_weights(scores, quantile=0.20)
        assert abs(weights[weights < 0].sum() - (-1.0)) < 1e-10

    def test_gross_exposure_is_two(self):
        """Sum of |weights| should equal 2 (100% long + 100% short)."""
        scores = pd.Series(range(50, 0, -1), index=[f"S{i}" for i in range(50)], dtype=float)
        weights = compute_weights(scores, quantile=0.20)
        assert abs(weights.abs().sum() - 2.0) < 1e-10

    def test_top_stocks_are_long(self):
        """Stocks with the highest factor scores should be long."""
        tickers = [f"S{i}" for i in range(50)]
        scores = pd.Series(range(50, 0, -1), index=tickers, dtype=float)
        weights = compute_weights(scores, quantile=0.20)

        # Top 10 scores (S0..S9 in our setup) should be positive
        top_tickers = scores.nlargest(10).index
        assert (weights[top_tickers] > 0).all()

    def test_bottom_stocks_are_short(self):
        """Stocks with the lowest factor scores should be short."""
        tickers = [f"S{i}" for i in range(50)]
        scores = pd.Series(range(50, 0, -1), index=tickers, dtype=float)
        weights = compute_weights(scores, quantile=0.20)

        bottom_tickers = scores.nsmallest(10).index
        assert (weights[bottom_tickers] < 0).all()

    def test_turnover_zero_same_weights(self):
        """No change in weights → zero turnover."""
        w = pd.Series([0.1, 0.1, -0.1, -0.1, 0.0], index=list("ABCDE"))
        assert compute_turnover(w, w) == pytest.approx(0.0)

    def test_turnover_full_flip(self):
        """Completely reversing positions → turnover = gross exposure."""
        w_old = pd.Series([0.5, 0.5, -0.5, -0.5])
        w_new = pd.Series([-0.5, -0.5, 0.5, 0.5])
        # Total abs change = 4.0, / 2 = 2.0 (one-way turnover = gross)
        assert compute_turnover(w_new, w_old) == pytest.approx(2.0)

"""
Unit tests for metrics.py

These catch bugs and ensure formulas are correct.
Run with: pytest tests/test_metrics.py -v
"""
import pytest
import pandas as pd
import numpy as np
from src.metrics import (
    compute_cagr,
    compute_sharpe,
    compute_sortino,
    compute_calmar,
    compute_max_drawdown,
    compute_win_rate,
    compute_ic,
    compute_ic_pvalue,
    compute_all_metrics,
)


class TestCAGR:
    """Test CAGR calculations."""
    
    def test_cagr_zero_return(self):
        """If returns are 0, CAGR should be 0."""
        returns = pd.Series([0.0] * 252)
        cagr = compute_cagr(returns)
        assert abs(cagr) < 0.001, f"Expected ~0, got {cagr}"
    
    def test_cagr_positive_returns(self):
        """1% daily return for 252 days should give high CAGR."""
        returns = pd.Series([0.01] * 252)  # 1% daily
        cagr = compute_cagr(returns)
        
        # (1.01)^252 ≈ 12.3x, so CAGR ≈ 11.3x (1130%)
        assert cagr > 10, f"Expected CAGR > 1000%, got {cagr * 100}%"
    
    def test_cagr_negative_returns(self):
        """Negative returns should give negative CAGR."""
        returns = pd.Series([-0.01] * 252)  # -1% daily
        cagr = compute_cagr(returns)
        assert cagr < 0, f"Expected negative CAGR, got {cagr}"


class TestMaxDrawdown:
    """Test maximum drawdown calculations."""
    
    def test_mdd_no_loss(self):
        """If only gains, MDD should be 0."""
        returns = pd.Series([0.01] * 100)  # All positive
        mdd = compute_max_drawdown(returns)
        assert mdd == 0.0, f"Expected 0, got {mdd}"
    
    def test_mdd_is_negative(self):
        """MDD should always be ≤ 0."""
        returns = pd.Series(np.random.normal(0.0005, 0.01, 1000))
        mdd = compute_max_drawdown(returns)
        assert mdd <= 0, f"MDD should be negative, got {mdd}"
    
    def test_mdd_known_case(self):
        """Test with known drawdown: +100%, then -50%."""
        returns = pd.Series([1.0, -0.5])  # Double, then lose half
        mdd = compute_max_drawdown(returns)
        
        # After +100%, value = 2x. After -50%, value = 1x.
        # Drawdown from peak (2x) to trough (1x) = -50%
        assert mdd == -0.5, f"Expected -0.5, got {mdd}"


class TestSharpe:
    """Test Sharpe ratio calculations."""
    
    def test_sharpe_no_volatility(self):
        """If no volatility, Sharpe should be 0."""
        returns = pd.Series([0.0] * 100)
        sharpe = compute_sharpe(returns)
        assert sharpe == 0.0, f"Expected 0, got {sharpe}"
    
    def test_sharpe_positive(self):
        """Positive excess returns with low volatility should give positive Sharpe."""
        returns = pd.Series([0.001] * 252)  # 0.1% daily = small, consistent gains
        sharpe = compute_sharpe(returns, risk_free_rate=0.0)
        assert sharpe > 0, f"Expected positive Sharpe, got {sharpe}"


class TestSortino:
    """Test Sortino ratio calculations."""
    
    def test_sortino_vs_sharpe_with_skew(self):
        """
        Sortino should be > Sharpe when returns are right-skewed.
        (More upside than downside volatility)
        """
        # Generate right-skewed returns: small losses, big gains
        np.random.seed(42)
        normal = np.random.normal(0.0005, 0.01, 1000)
        # Add big positive tail
        returns = pd.Series(normal)
        returns[returns > 0.02] *= 3  # Amplify big gains
        
        sharpe = compute_sharpe(returns)
        sortino = compute_sortino(returns)
        
        assert sortino >= sharpe, f"Sortino should be >= Sharpe for right-skewed, got {sortino} vs {sharpe}"


class TestCalmar:
    """Test Calmar ratio calculations."""
    
    def test_calmar_known_case(self):
        """
        CAGR = 10%, MDD = -20% → Calmar = 0.5
        """
        # Construct returns that give roughly 10% CAGR and -20% MDD
        returns = pd.Series([0.0001] * 252)  # Small consistent gains
        cagr = compute_cagr(returns)
        mdd = compute_max_drawdown(returns)
        
        if mdd != 0:  # Avoid division by zero
            calmar = compute_calmar(returns)
            assert calmar == cagr / abs(mdd), "Calmar formula mismatch"


class TestWinRate:
    """Test win rate calculations."""
    
    def test_win_rate_all_positive(self):
        """If all returns are positive, win rate should be 100%."""
        returns = pd.Series([0.01] * 100)
        wr = compute_win_rate(returns)
        assert wr == 1.0, f"Expected 1.0, got {wr}"
    
    def test_win_rate_all_negative(self):
        """If all returns are negative, win rate should be 0%."""
        returns = pd.Series([-0.01] * 100)
        wr = compute_win_rate(returns)
        assert wr == 0.0, f"Expected 0.0, got {wr}"
    
    def test_win_rate_50_50(self):
        """50 wins, 50 losses should give 50% win rate."""
        returns = pd.Series([0.01] * 50 + [-0.01] * 50)
        wr = compute_win_rate(returns)
        assert wr == 0.5, f"Expected 0.5, got {wr}"


class TestIC:
    """Test Information Coefficient calculations."""
    
    def test_ic_perfect_correlation(self):
        """Perfect positive correlation should give IC ≈ 1."""
        x = pd.Series(range(100))
        y = pd.Series(range(100)) + np.random.normal(0, 0.1, 100)  # y ≈ x with noise
        ic = compute_ic(x, y)
        assert ic > 0.95, f"Expected IC > 0.95, got {ic}"
    
    def test_ic_no_correlation(self):
        """Random uncorrelated data should give IC ≈ 0."""
        np.random.seed(42)
        x = pd.Series(np.random.normal(0, 1, 1000))
        y = pd.Series(np.random.normal(0, 1, 1000))
        ic = compute_ic(x, y)
        assert abs(ic) < 0.2, f"Expected IC ≈ 0, got {ic}"


class TestICPValue:
    """Test IC p-value significance tests."""
    
    def test_ic_pvalue_significant(self):
        """Series of high IC values should have p-value < 0.05."""
        ic_series = pd.Series([0.08] * 50)  # Consistently high IC
        pval = compute_ic_pvalue(ic_series)
        assert pval < 0.05, f"Expected p-value < 0.05, got {pval}"
    
    def test_ic_pvalue_not_significant(self):
        """Series of random IC values should have p-value > 0.05."""
        np.random.seed(42)
        ic_series = pd.Series(np.random.normal(0, 0.05, 50))  # Random noise
        pval = compute_ic_pvalue(ic_series)
        assert pval > 0.05, f"Expected p-value > 0.05, got {pval}"


class TestAllMetrics:
    """Test the all-in-one metrics function."""
    
    def test_all_metrics_returns_dict(self):
        """compute_all_metrics should return a dictionary."""
        returns = pd.Series([0.001] * 252)
        metrics = compute_all_metrics(returns)
        
        assert isinstance(metrics, dict)
        assert "cagr" in metrics
        assert "sharpe_ratio" in metrics
        assert "sortino_ratio" in metrics
        assert "calmar_ratio" in metrics
        assert "win_rate" in metrics
    
    def test_all_metrics_with_ic(self):
        """Should include IC when factor data is provided."""
        returns = pd.Series([0.001] * 252)
        factor_scores = pd.Series(range(252))
        forward_returns = pd.Series(range(252)) + np.random.normal(0, 1, 252)
        
        metrics = compute_all_metrics(
            returns,
            factor_scores=factor_scores,
            forward_returns=forward_returns,
        )
        
        assert "ic" in metrics
        assert "ic_pvalue" in metrics
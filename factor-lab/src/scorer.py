"""
scorer.py — per-ticker analysis for the /api/analyze endpoint.

Returns comprehensive analysis for a single equity ticker including:
- Basic price/availability info
- Factor score and momentum
- Macro context (10Y yield, sector)
- News sentiment (using FinBERT if available, keyword matching fallback)
- Final verdict (buy/hold/sell)

SENTIMENT ANALYSIS:
===================
The sentiment analysis uses FinBERT (Financial BERT) if available:
- FinBERT: Deep learning model fine-tuned for financial sentiment (~80%+ accuracy)
- Fallback: Keyword matching (lightweight, always available)

To enable FinBERT:
$ pip install transformers torch

FinBERT will be automatically loaded on first sentiment analysis request.
First load takes ~10 seconds (model download + initialization).
Subsequent requests are faster (~500ms per headline on CPU).
"""

import yfinance as yf
import numpy as np
import pandas as pd
from src.data import download_prices
from src.factors import momentum_12_1
from src.macro import get_macro_context
from src.sentiment import get_news_sentiment


def _calculate_rsi(prices_series, period=14):
    """
    Calculate Relative Strength Index (RSI).
    
    RSI measures momentum by comparing magnitude of recent gains to recent losses.
    Scale: 0-100
    - RSI < 30: Oversold (potentially buy signal)
    - RSI > 70: Overbought (potentially sell signal)
    - 30-70: Neutral
    
    Parameters
    ----------
    prices_series : pd.Series
        Price data (typically closing prices)
    period : int
        Period for RSI calculation (default 14)
    
    Returns
    -------
    float : RSI value (0-100)
    """
    try:
        delta = prices_series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Return the most recent RSI value
        return float(rsi.iloc[-1])
    except Exception:
        return 50.0  # Default to neutral if calculation fails


def _calculate_rsi_score(rsi_value):
    """
    Convert RSI (0-100) to a buy/sell score (0-100).
    
    Scoring:
    - RSI < 30 (oversold): Good buy signal → score 70-90
    - RSI 30-50: Weak buy → score 50-70
    - RSI 50-70: Neutral to weak sell → score 30-50
    - RSI > 70 (overbought): Sell signal → score 10-30
    
    Parameters
    ----------
    rsi_value : float
        RSI value (0-100)
    
    Returns
    -------
    dict with score, label, and explanation
    """
    if rsi_value < 30:
        rsi_score = 75 + (30 - rsi_value) / 3  # 75-85
        label = "Oversold - Buy Signal"
        explanation = f"RSI {rsi_value:.1f} - Stock is oversold. Potential buying opportunity."
    elif rsi_value < 50:
        rsi_score = 50 + (50 - rsi_value) / 2  # 50-75
        label = "Weak Buy"
        explanation = f"RSI {rsi_value:.1f} - Momentum is weak but improving."
    elif rsi_value < 70:
        rsi_score = 50 - (rsi_value - 50) / 2  # 25-50
        label = "Neutral to Weak Sell"
        explanation = f"RSI {rsi_value:.1f} - Momentum is rising but not yet overbought."
    else:
        rsi_score = max(10, 30 - (rsi_value - 70) / 3)  # 10-30
        label = "Overbought - Sell Signal"
        explanation = f"RSI {rsi_value:.1f} - Stock is overbought. Consider taking profits."
    
    return {
        "rsi_value": round(rsi_value, 1),
        "score": int(rsi_score),
        "label": label,
        "explanation": explanation,
    }


def _calculate_entry_exit_levels(prices_series: pd.Series, current_price: float) -> dict:
    """
    Calculate technical entry/exit watch *zones* rather than single-point levels.

    The zones are still heuristic and educational, but they are more honest than
    returning one exact price.  Each zone is centered around a technical anchor
    (moving averages, current price, or 52-week high) with an adaptive width
    based on recent realised volatility.

    Entry watch zones (potential support / accumulation areas):
    - Conservative : around 200-day moving average
    - Moderate     : around 50-day moving average
    - Aggressive   : around current price (momentum entry)

    Exit watch zones (potential resistance / profit-taking areas):
    - Conservative : modest upside from current price / 50-day MA
    - Moderate     : stronger upside extension
    - Ambitious    : prior 52-week high or stronger upside extension

    These are still reference zones, not trade signals.
    """
    try:
        history_252 = prices_series.tail(252)
        history_50 = prices_series.tail(50)
        history_200 = prices_series.tail(200)

        high_52w = history_252.max()
        low_52w = history_252.min()
        ma_50 = history_50.mean()
        ma_200 = history_200.mean()

        recent_returns = prices_series.pct_change().dropna().tail(20)
        recent_volatility = float(recent_returns.std()) if not recent_returns.empty else 0.02
        zone_width_pct = min(0.06, max(0.015, recent_volatility * 2.5))

        def make_zone(anchor: float, label: str, basis: str, zone_type: str, cap_to_current: bool = False) -> dict:
            low = anchor * (1 - zone_width_pct)
            high = anchor * (1 + zone_width_pct)

            if zone_type == "entry" and cap_to_current:
                high = min(high, current_price)
                low = min(low, high)

            if zone_type == "exit":
                low = max(low, current_price)
                high = max(high, low)

            return {
                "label": label,
                "basis": basis,
                "anchor": round(anchor, 2),
                "low": round(low, 2),
                "high": round(high, 2),
                "range_label": f"${low:.2f} - ${high:.2f}",
            }

        trend = "uptrend" if current_price >= ma_50 >= ma_200 else "downtrend" if current_price <= ma_50 <= ma_200 else "mixed"

        entry_conservative_anchor = min(ma_200, current_price)
        entry_moderate_anchor = min(ma_50, current_price)
        entry_aggressive_anchor = current_price

        exit_conservative_anchor = max(current_price * 1.03, ma_50)
        exit_moderate_anchor = max(exit_conservative_anchor * 1.03, current_price * 1.08, ma_200 * 1.05)
        exit_ambitious_anchor = max(exit_moderate_anchor * 1.03, high_52w, current_price * 1.15)

        return {
            "current": round(current_price, 2),
            "zone_width_pct": round(zone_width_pct * 100, 2),
            "trend_context": trend,
            "entry_watch_zones": {
                "conservative": make_zone(
                    anchor=entry_conservative_anchor,
                    label="Conservative",
                    basis="200-day moving average support",
                    zone_type="entry",
                    cap_to_current=True,
                ),
                "moderate": make_zone(
                    anchor=entry_moderate_anchor,
                    label="Moderate",
                    basis="50-day moving average support",
                    zone_type="entry",
                    cap_to_current=True,
                ),
                "aggressive": make_zone(
                    anchor=entry_aggressive_anchor,
                    label="Aggressive",
                    basis="Current price / momentum continuation",
                    zone_type="entry",
                    cap_to_current=False,
                ),
            },
            "exit_watch_zones": {
                "conservative": make_zone(
                    anchor=exit_conservative_anchor,
                    label="Conservative",
                    basis="Initial upside objective above current price",
                    zone_type="exit",
                ),
                "moderate": make_zone(
                    anchor=exit_moderate_anchor,
                    label="Moderate",
                    basis="Extended upside objective",
                    zone_type="exit",
                ),
                "ambitious": make_zone(
                    anchor=exit_ambitious_anchor,
                    label="Ambitious",
                    basis="52-week high / breakout resistance",
                    zone_type="exit",
                ),
            },
            "week_52_high": round(high_52w, 2),
            "week_52_low": round(low_52w, 2),
            "ma_50": round(ma_50, 2),
            "ma_200": round(ma_200, 2),
            "summary": (
                f"These watch zones are centered on moving averages and recent price structure, "
                f"with a volatility buffer of {round(zone_width_pct * 100, 2)}%."
            ),
            "disclaimer": (
                "These are technical watch zones for context, not buy/sell recommendations. "
                "Use them with trend, fundamentals, and risk management."
            ),
        }
    except Exception as e:
        print(f"Error calculating entry/exit levels: {e}")
        return {"error": str(e)}


def _calculate_stock_correlation(ticker: str, compare_to: list = None) -> dict:
    """
    Calculate correlation between ticker and other market baskets.
    
    Correlation shows how much a stock moves together with market indices.
    - 1.0 = Moves exactly same as market
    - 0.5 = Moves somewhat with market
    - 0.0 = No relationship
    - -1.0 = Moves opposite to market (hedging asset)
    
    Parameters
    ----------
    ticker : str
        Main ticker to analyze
    compare_to : list
        List of market indices to compare against
        Default: VOO (S&P 500), QQQ (Tech), IWM (Small caps)
    
    Returns
    -------
    dict with correlation values and beginner-friendly interpretation
    """
    if compare_to is None:
        # VOO = S&P 500 large companies
        # QQQ = Tech companies (NASDAQ)
        # IWM = Small companies (Russell 2000)
        compare_to = ['VOO', 'QQQ', 'IWM']
    
    try:
        # Fetch price data for all tickers
        all_tickers = [ticker] + compare_to
        prices = download_prices(tickers=all_tickers, start="2024-01-01")
        
        if prices.empty or ticker not in prices.columns:
            return {"error": f"Could not fetch price data for {ticker}"}
        
        # Calculate daily returns
        returns = prices.pct_change().dropna()
        
        # Calculate correlations with explanations
        correlations = {}
        correlation_explanations = {}
        
        for other_ticker in compare_to:
            if other_ticker in returns.columns:
                corr = returns[ticker].corr(returns[other_ticker])
                corr_rounded = round(corr, 2)
                correlations[other_ticker] = corr_rounded
                
                # Beginner explanation for each correlation
                if other_ticker == 'VOO':
                    market_type = "Overall Market (Large Companies)"
                elif other_ticker == 'QQQ':
                    market_type = "Tech Sector"
                else:  # IWM
                    market_type = "Small Companies"
                
                if corr_rounded > 0.75:
                    explanation = f"Moves closely with {market_type}"
                elif corr_rounded > 0.5:
                    explanation = f"Somewhat follows {market_type}"
                elif corr_rounded > 0.25:
                    explanation = f"Weakly follows {market_type}"
                elif corr_rounded > 0:
                    explanation = f"Barely follows {market_type}"
                else:
                    explanation = f"Moves opposite to {market_type} (Hedging asset)"
                
                correlation_explanations[other_ticker] = explanation
        
        # Compute average correlation
        avg_corr = np.mean(list(correlations.values())) if correlations else 0
        avg_corr_rounded = round(avg_corr, 2)
        
        # Overall beginner interpretation
        if avg_corr_rounded > 0.7:
            overall_interpretation = "📊 This stock moves with the overall market. When market goes up, this usually goes up too."
        elif avg_corr_rounded > 0.4:
            overall_interpretation = "📊 This stock somewhat follows the market, but has its own personality."
        elif avg_corr_rounded > 0:
            overall_interpretation = "📊 This stock mostly does its own thing (good for diversification)."
        else:
            overall_interpretation = "📊 This stock often moves opposite to the market (great for hedging/protection)."
        
        return {
            "ticker": ticker,
            "correlations": correlations,
            "correlation_explanations": correlation_explanations,
            "average_correlation": avg_corr_rounded,
            "overall_interpretation": overall_interpretation,
        }
    
    except Exception as e:
        print(f"Error calculating correlation: {e}")
        return {"error": str(e)}


def analyze_ticker(ticker: str) -> dict:
    """
    Return comprehensive analysis dict for a single ticker.

    Parameters
    ----------
    ticker : str
        Equity ticker symbol, e.g. ``"NVDA"``.

    Returns
    -------
    dict with keys:
        ticker       : the (uppercased) ticker symbol requested
        company      : company name from yfinance
        in_universe  : bool — True if price data was found
        latest_price : float or None — most-recent adjusted close price
        verdict      : "green", "yellow", or "red"
        factor       : dict with score, label, momentum, rsi
        macro        : dict with VIX, yield, sector context
        sentiment    : dict with sentiment counts and summary
    """
    ticker = ticker.upper().strip()

    # 1. Fetch price data
    try:
        prices = download_prices(tickers=[ticker], start="2020-01-01")
    except Exception as exc:
        return {
            "ticker": ticker,
            "company": ticker,
            "in_universe": False,
            "error": f"Error fetching price data for {ticker}: {exc}",
        }

    if ticker not in prices.columns or prices[ticker].dropna().empty:
        return {
            "ticker": ticker,
            "company": ticker,
            "in_universe": False,
            "error": f"No price data found for {ticker}.",
        }

    series = prices[ticker].dropna()
    latest_price = float(series.iloc[-1])

    # 2. Get company name
    try:
        info = yf.Ticker(ticker).info
        company_name = info.get("longName") or info.get("shortName") or ticker
    except Exception:
        company_name = ticker

    # 3. Compute factor score
    factor = _compute_factor_score(ticker, prices)

    # 4. Get macro context
    macro = get_macro_context(ticker)

    # 5. Get sentiment (using FinBERT if available, fallback to keyword matching)
    sentiment = get_news_sentiment(ticker, company_name, use_finbert=True)

    # 6. Compute verdict
    verdict = _compute_verdict(factor, macro, sentiment)
    
    # 7. Calculate entry/exit price levels
    entry_exit = _calculate_entry_exit_levels(series, latest_price)
    
    # 8. Calculate stock correlation with market indices
    correlation = _calculate_stock_correlation(ticker)

    return {
        "ticker": ticker,
        "company": company_name,
        "in_universe": True,
        "latest_price": round(latest_price, 2),
        "verdict": verdict,
        "factor": factor,
        "macro": macro,
        "sentiment": sentiment,
        "entry_exit": entry_exit,
        "correlation": correlation,
    }


def _compute_factor_score(ticker: str, prices) -> dict:
    """
    Compute momentum and RSI factor score for the ticker.
    
    Returns a weighted score combining:
    1. Momentum Factor (12-month): 50% weight
       - Measures 12-month price return excluding the most recent month
       - Range: -1.0 (worst performer) to +1.0 (best performer)
    
    2. RSI Factor (14-day): 50% weight
       - Relative Strength Index measuring momentum
       - RSI < 30: Oversold (buy signal)
       - RSI > 70: Overbought (sell signal)
    
    Final Score: 0-100
    - 75+: Strong buy signal
    - 60-75: Good buy signal
    - 40-60: Neutral/Hold
    - 25-40: Weak sell signal
    - 0-25: Strong sell signal
    """
    try:
        # 1. Compute 12-month momentum score
        momentum = momentum_12_1(prices)
        momentum_value = momentum[ticker].dropna().iloc[-1]
        momentum_score = max(0, min(100, (momentum_value + 1) * 50))
        
        # 2. Compute RSI score
        price_series = prices[ticker].dropna()
        rsi_value = _calculate_rsi(price_series, period=14)
        rsi_dict = _calculate_rsi_score(rsi_value)
        rsi_score = rsi_dict["score"]
        
        # 3. Combine scores: 50% momentum + 50% RSI
        final_score = (momentum_score * 0.5 + rsi_score * 0.5)
        final_score = max(0, min(100, final_score))
        
        # Determine label
        if final_score >= 75:
            label = "Very Strong - Both Momentum & RSI Bullish"
        elif final_score >= 60:
            label = "Strong - Good Buy Signal"
        elif final_score >= 50:
            label = "Moderate Momentum"
        elif final_score >= 40:
            label = "Weak - Mixed Signals"
        elif final_score >= 25:
            label = "Negative - Bearish Signals"
        else:
            label = "Very Weak - Strong Sell Signal"
        
        return {
            "score": int(final_score),
            "label": label,
            "momentum": round(float(momentum_value), 2),
            "momentum_score": int(momentum_score),
            "rsi": rsi_dict,
            "explanation": f"12-month momentum ({int(momentum_score)}/100) + 14-day RSI ({int(rsi_score)}/100) = {int(final_score)}/100. Higher = more bullish.",
        }
    except Exception as e:
        return {
            "score": 50,
            "label": "Neutral",
            "momentum": 0.0,
            "momentum_score": 50,
            "rsi": {
                "rsi_value": 50.0,
                "score": 50,
                "label": "Error",
                "explanation": f"Could not calculate RSI: {e}",
            },
            "explanation": "Could not calculate factor score.",
        }


def _compute_verdict(factor: dict, macro: dict, sentiment: dict) -> str:
    """Compute overall verdict: 'green' (buy), 'yellow' (hold), or 'red' (sell)."""
    score = 0

    # Factor score contribution (0-30 points)
    factor_score = factor.get("score", 50)
    if factor_score >= 70:
        score += 10
    elif factor_score >= 50:
        score += 5
    elif factor_score < 30:
        score -= 10

    # Macro context contribution (0-30 points)
    # VIX: Lower VIX = calm markets = good time to buy
    # Higher VIX = scared markets = be cautious
    vix = macro.get("vix")
    if vix and vix < 15:
        score += 10  # Market calm, good buying opportunity
    elif vix and vix < 25:
        score += 5  # Normal conditions
    elif vix and vix > 30:
        score -= 8  # Market nervous, be careful

    # Sector signal
    sector_signal = macro.get("sector_signal", "neutral").lower()
    if "strong" in sector_signal:
        score += 5
    elif "weak" in sector_signal:
        score -= 5

    # Sentiment contribution (0-30 points)
    sentiment_pos = sentiment.get("positive", 0)
    sentiment_neg = sentiment.get("negative", 0)
    sentiment_neu = sentiment.get("neutral", 0)
    total_sentiment = sentiment_pos + sentiment_neg + sentiment_neu

    if total_sentiment > 0:
        pos_ratio = sentiment_pos / total_sentiment
        if pos_ratio > 0.5:
            score += 8
        elif pos_ratio < 0.2:
            score -= 8

    # Determine verdict based on total score
    if score >= 8:
        return "green"
    elif score <= -8:
        return "red"
    else:
        return "yellow"

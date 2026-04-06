"""
scorer.py — per-ticker analysis for the /api/analyze endpoint.

Returns comprehensive analysis for a single equity ticker including:
- Basic price/availability info
- Factor score and momentum
- Macro context (VIX, yield, sector)
- News sentiment
- Final verdict (buy/hold/sell)
"""

import yfinance as yf
from src.data import download_prices
from src.factors import momentum_12_1
from src.macro import get_macro_context
from src.sentiment import get_news_sentiment


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
        factor       : dict with score, label, momentum
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

    # 5. Get sentiment
    sentiment = get_news_sentiment(ticker, company_name)

    # 6. Compute verdict
    verdict = _compute_verdict(factor, macro, sentiment)

    return {
        "ticker": ticker,
        "company": company_name,
        "in_universe": True,
        "latest_price": round(latest_price, 2),
        "verdict": verdict,
        "factor": factor,
        "macro": macro,
        "sentiment": sentiment,
    }


def _compute_factor_score(ticker: str, prices) -> dict:
    """Compute momentum factor score for the ticker."""
    try:
        momentum = momentum_12_1(prices)
        score_value = momentum[ticker].dropna().iloc[-1]
        
        # Normalize to 0-100 scale
        score = max(0, min(100, (score_value + 1) * 50))
        
        if score >= 70:
            label = "Strong Momentum"
        elif score >= 50:
            label = "Moderate Momentum"
        elif score >= 30:
            label = "Weak Momentum"
        else:
            label = "Negative Momentum"
        
        return {
            "score": int(score),
            "label": label,
            "momentum": round(float(score_value), 2),
        }
    except Exception:
        return {
            "score": 50,
            "label": "Neutral",
            "momentum": 0.0,
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
    # COMMENTED OUT: VIX calculations disabled
    # vix = macro.get("vix")
    # if vix and vix < 20:
    #     score += 8
    # elif vix and vix > 30:
    #     score -= 8

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

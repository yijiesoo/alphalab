"""
Beginner-friendly explanations and portfolio recommendations.
Converts technical analysis into plain English for beginners.
"""

import yfinance as yf
import pandas as pd
from typing import Dict, List, Tuple


# ========== SIMPLIFIED TERMINOLOGY MAPPINGS ==========

SIMPLE_TERMS = {
    "momentum": "Buying Pressure",
    "rsi": "Strength Meter",
    "macd": "Trend Direction",
    "vix": "Market Fear Level",
    "yield": "Interest Rate",
    "volatility": "Price Swings",
    "correlation": "Price Movement Pattern",
    "sharpe_ratio": "Risk-Adjusted Return",
}

SIGNAL_EMOJI = {
    "strong_buy": "🟢 STRONG BUY",
    "buy": "🟡 BUY",
    "hold": "🔵 HOLD",
    "sell": "🔴 SELL",
}


# ========== SCORE TO BEGINNER-FRIENDLY VERDICT ==========

def get_verdict_with_emoji(score: float) -> Dict[str, str]:
    """
    Convert numerical score to beginner-friendly verdict with emoji.
    
    Parameters
    ----------
    score : float
        Score from 0-100
        
    Returns
    -------
    dict with 'verdict', 'emoji', and 'explanation'
    """
    if score >= 80:
        return {
            "verdict": "STRONG BUY",
            "emoji": "🟢",
            "explanation": "Everything looks very good. Strong signs this stock will go up."
        }
    elif score >= 60:
        return {
            "verdict": "BUY",
            "emoji": "🟡",
            "explanation": "Good signs. Positive momentum and sentiment. Good time to consider buying."
        }
    elif score >= 40:
        return {
            "verdict": "HOLD",
            "emoji": "🔵",
            "explanation": "Mixed signals. Wait for better entry point. No strong reason to buy or sell."
        }
    else:
        return {
            "verdict": "SELL",
            "emoji": "🔴",
            "explanation": "Weak signals. Price momentum is down. Consider selling or avoiding."
        }


# ========== CONFIDENCE SCORING ==========

def calculate_confidence(analysis_data: Dict) -> Dict:
    """
    Calculate how confident we are in the signal (0-100%).
    
    Factors:
    1. Score extremeness (how far from 50)
    2. Signal agreement (do momentum, sentiment, macro all agree?)
    3. Data quality (is there enough data?)
    
    Parameters
    ----------
    analysis_data : dict
        Output from analyze_ticker or API
        
    Returns
    -------
    dict with confidence score, reasoning, and warnings
    """
    factor = analysis_data.get("factor", {})
    score = factor.get("score", 50) if isinstance(factor, dict) else 50
    
    # Count how many signals align
    signal_agreement = 0
    signals_count = 0
    
    # 1. Momentum signal
    momentum = factor.get("momentum", 0) if isinstance(factor, dict) else 0
    signals_count += 1
    if (score > 60 and momentum > 0) or (score < 40 and momentum < 0):
        signal_agreement += 1
    
    # 2. Sentiment signal
    sentiment = analysis_data.get("sentiment", {})
    signals_count += 1
    if isinstance(sentiment, dict):
        sentiment_score = sentiment.get("score", 0)
        if (score > 60 and sentiment_score > 0) or (score < 40 and sentiment_score < 0):
            signal_agreement += 1
    
    # 3. Macro signal
    macro = analysis_data.get("macro", {})
    signals_count += 1
    if isinstance(macro, dict):
        vix = macro.get("vix", 20)
        # In low VIX (calm market), buy signals are more reliable
        if score > 60 and vix < 20:
            signal_agreement += 1
        elif score < 40 and vix > 20:
            signal_agreement += 1
    
    # Calculate confidence
    extremeness = abs(score - 50) / 50  # 0-1: how extreme is the score?
    agreement = signal_agreement / signals_count if signals_count > 0 else 0.5  # 0-1: alignment
    
    # Final confidence: 60% from extremeness, 40% from agreement
    base_confidence = (extremeness * 0.6 + agreement * 0.4) * 100
    
    # Cap at 95% to show appropriate humility
    confidence = min(base_confidence, 95)
    
    # Generate explanation
    if confidence < 50:
        confidence_label = "Low - Mixed signals"
    elif confidence < 70:
        confidence_label = "Medium - Some agreement"
    else:
        confidence_label = "High - Strong signals"
    
    return {
        "confidence": round(confidence, 0),
        "confidence_label": confidence_label,
        "factors_aligned": signal_agreement,
        "factors_total": signals_count,
        "explanation": f"{signal_agreement}/{signals_count} signals agree ({confidence_label})"
    }


# ========== GENERATE WARNINGS ==========

def generate_warnings(analysis_data: Dict) -> List[str]:
    """
    Generate beginner-friendly warnings for the user.
    
    Parameters
    ----------
    analysis_data : dict
        Output from analyze_ticker or API
        
    Returns
    -------
    list of warning strings
    """
    warnings = []
    
    # 1. Low confidence warning
    confidence = calculate_confidence(analysis_data)
    if confidence["confidence"] < 50:
        warnings.append(
            "⚠️ Low confidence signal - Signals are mixed. Be extra careful with this trade."
        )
    
    # 2. High volatility warning
    macro = analysis_data.get("macro", {})
    if isinstance(macro, dict):
        vix = macro.get("vix", 15)
        if vix > 25:
            warnings.append(
                "⚠️ Market is nervous (VIX > 25). Stock prices could jump around dramatically."
            )
        elif vix > 30:
            warnings.append(
                "🚨 Market is very fearful (VIX > 30). Extra risky time to trade. Consider waiting."
            )
    
    # 3. Weak signal warning
    factor = analysis_data.get("factor", {})
    score = factor.get("score", 50) if isinstance(factor, dict) else 50
    if 40 <= score <= 60:
        warnings.append(
            "💭 Signal is neutral (around 50/100). Not a strong reason to buy or sell yet."
        )
    
    # 4. Sentiment disagreement
    sentiment = analysis_data.get("sentiment", {})
    if isinstance(sentiment, dict):
        sent_score = sentiment.get("score", 0)
        if (score > 60 and sent_score < 0) or (score < 40 and sent_score > 0):
            warnings.append(
                "⚡ Sentiment disagrees with the score. News sentiment is not aligned with technical signals."
            )
    
    return warnings


# ========== WHY THIS SIGNAL EXPLANATION ==========

def explain_signal(analysis_data: Dict) -> Dict:
    """
    Explain in plain English why the app recommends buy/sell.
    
    Parameters
    ----------
    analysis_data : dict
        Output from /api/analyze endpoint
        
    Returns
    -------
    dict with detailed explanation including confidence, warnings, and tips
    """
    # Get score from factor dict (contains 'score' key)
    factor = analysis_data.get("factor", {})
    score = factor.get("score", 50) if isinstance(factor, dict) else 50
    
    # Calculate confidence
    confidence = calculate_confidence(analysis_data)
    
    # Generate warnings
    warnings = generate_warnings(analysis_data)
    
    explanation = {
        "score": score,  # Keep numerical score for comparison
        "confidence": confidence,  # Add confidence breakdown
        "verdict": get_verdict_with_emoji(score),  # Add beginner-friendly verdict
        "momentum": _format_momentum(factor),
        "rsi": _format_rsi(factor),  # NEW: Add RSI strength indicator
        "sentiment": _format_sentiment(analysis_data.get("sentiment", {})),
        "macro": _format_macro(analysis_data.get("macro", {})),
        "overall": "",
        "warnings": warnings,  # Use calculated warnings
        "tips": []
    }
    
    # Overall explanation
    verdict = explanation["verdict"]
    confidence_text = f" ({confidence['confidence']}% confidence)" if confidence["confidence"] else ""
    explanation["overall"] = f"{verdict['emoji']} {verdict['explanation']}{confidence_text}"
    
    # Add beginner-friendly tips
    if score > 70:
        explanation["tips"].append("💡 If you buy, diversify: Don't put all money in one stock")
        explanation["tips"].append("📅 Dollar-Cost Average: Buy in 3-4 portions over 2-4 weeks instead of all at once")
    elif score < 40:
        explanation["tips"].append("⚠️ Consider waiting for a better entry point or skip this stock")
        explanation["tips"].append("� This is NOT a recommendation to sell - only to be cautious")
    else:
        explanation["tips"].append("💭 Mixed signals - do your own research before buying")
        explanation["tips"].append("� Wait for a clearer signal (score above 70 or below 30)")
    
    explanation["tips"].append("🎯 This is a tool to help, not a guarantee. Always invest responsibly.")
    
    return explanation
    
    return explanation


def _format_momentum(factor: Dict) -> Dict:
    """Format momentum explanation as dict with strength and text."""
    if not factor:
        return {"strength": "WEAK", "text": "⏳ Price trend: Not enough data yet"}
    
    # New: Include both momentum and RSI
    momentum_score = factor.get("momentum_score", 0)
    
    # Get RSI information
    rsi_dict = factor.get("rsi", {})
    rsi_value = rsi_dict.get("rsi_value", 50)
    
    if momentum_score >= 70:
        return {
            "strength": "STRONG",
            "text": f"🔥 Price Trend: STRONG ({momentum_score}/100) - Uptrend is very strong. RSI: {rsi_value:.1f}"
        }
    elif momentum_score >= 50:
        return {
            "strength": "GOOD",
            "text": f"📈 Price Trend: GOOD ({momentum_score}/100) - Price is trending up. RSI: {rsi_value:.1f}"
        }
    elif momentum_score >= 30:
        return {
            "strength": "WEAK",
            "text": f"➡️ Price Trend: WEAK ({momentum_score}/100) - Price is sideways. RSI: {rsi_value:.1f}"
        }
    else:
        return {
            "strength": "VERY WEAK",
            "text": f"📉 Price Trend: VERY WEAK ({momentum_score}/100) - Price is trending down. RSI: {rsi_value:.1f}"
        }


def _format_sentiment(sentiment: Dict) -> Dict:
    """Format sentiment explanation as dict."""
    if not sentiment:
        return {
            "sentiment_type": "neutral",
            "text": "🤐 News Sentiment: Not enough news data"
        }
    
    positive = sentiment.get("positive", 0)
    negative = sentiment.get("negative", 0)
    neutral = sentiment.get("neutral", 0)
    total = positive + negative + neutral
    
    # If no headlines, return neutral
    if total == 0:
        return {
            "sentiment_type": "neutral",
            "text": "🤐 News Sentiment: Not enough news data"
        }
    
    # Calculate sentiment percentage
    pos_pct = positive / total if total > 0 else 0
    neg_pct = negative / total if total > 0 else 0
    
    if pos_pct >= 0.7:
        return {
            "sentiment_type": "positive",
            "text": f"👍 News Sentiment is VERY POSITIVE ({pos_pct:.0%}) - People are excited about this stock!"
        }
    elif pos_pct >= 0.5:
        return {
            "sentiment_type": "positive",
            "text": f"😊 News Sentiment is POSITIVE ({pos_pct:.0%}) - Good news coming out"
        }
    elif neg_pct >= 0.5:
        return {
            "sentiment_type": "negative",
            "text": f"� News Sentiment is NEGATIVE ({neg_pct:.0%}) - Bad news or concerns"
        }
    else:
        return {
            "sentiment_type": "neutral",
            "text": f"� News Sentiment is NEUTRAL ({neutral} neutral articles) - Mixed opinions"
        }


def _format_rsi(factor: Dict) -> Dict:
    """Format RSI explanation as dict with easy-to-understand terms."""
    if not factor:
        return {
            "strength": "NEUTRAL",
            "text": "Stream Price Momentum: Not enough data yet"
        }
    
    rsi_dict = factor.get("rsi", {})
    rsi_value = rsi_dict.get("rsi_value", 50)
    
    if rsi_value < 30:
        return {
            "strength": "OVERSOLD - BUY",
            "text": f"Green Stock Strength: {rsi_value:.1f}/100 - OVERSOLD (Stock is down, might bounce back - Good to buy)"
        }
    elif rsi_value < 50:
        return {
            "strength": "WEAK - SLIGHT BUY",
            "text": f"Yellow Stock Strength: {rsi_value:.1f}/100 - WEAK (Momentum improving but still not strong)"
        }
    elif rsi_value < 70:
        return {
            "strength": "STRONG - SLIGHT SELL",
            "text": f"Orange Stock Strength: {rsi_value:.1f}/100 - STRONG (Momentum is good but getting stretched)"
        }
    else:
        return {
            "strength": "OVERBOUGHT - SELL",
            "text": f"Red Stock Strength: {rsi_value:.1f}/100 - OVERBOUGHT (Stock up alot, might pull back - Consider selling)"
        }


def _format_macro(macro: Dict) -> Dict:
    """Format macro explanation as dict."""
    if not macro:
        return {"text": "🌍 Market Conditions: Unable to get data"}
    
    explanations = []
    
    # VIX explanation
    vix = macro.get("vix")
    if vix:
        try:
            vix_val = float(vix)
            if vix_val < 15:
                explanations.append("✅ VIX (Market Fear): CALM - People are confident (Good time to buy)")
            elif vix_val < 25:
                explanations.append("📊 VIX (Market Fear): NORMAL - Average conditions")
            else:
                explanations.append("⚠️ VIX (Market Fear): HIGH - People are nervous (Be careful)")
        except (ValueError, TypeError):
            pass
    
    # Yield explanation
    yield_10y = macro.get("yield_10y")
    if yield_10y:
        try:
            yield_val = float(yield_10y)
            if yield_val < 3:
                explanations.append(f"💰 Interest Rates: LOW at {yield_val}% (Stocks look attractive)")
            elif yield_val < 4:
                explanations.append(f"📈 Interest Rates: MODERATE at {yield_val}% (Normal conditions)")
            else:
                explanations.append(f"⚠️ Interest Rates: HIGH at {yield_val}% (Competition from bonds)")
        except (ValueError, TypeError):
            pass
    
    text = " | ".join(explanations) if explanations else "🌍 Market conditions: Mixed signals"
    return {"text": text}


# ========== PORTFOLIO RECOMMENDATIONS ==========

def get_portfolio_recommendation(current_portfolio: List[str], 
                                  new_stock: str = None) -> Dict:
    """
    Analyze portfolio and recommend allocation + suggest negatively correlated stocks.
    
    Parameters
    ----------
    current_portfolio : list
        List of tickers in user's portfolio (e.g., ["AAPL", "MSFT", "TSLA"])
    new_stock : str, optional
        New stock to add to portfolio
        
    Returns
    -------
    dict with:
        - allocation: recommended % per stock
        - risk_level: portfolio risk assessment
        - diversification: suggestions for negatively correlated stocks
        - total_stocks_needed: ideal number of stocks
    """
    
    if not current_portfolio:
        return {
            "allocation": {},
            "risk_level": "No Portfolio",
            "diversification": [],
            "total_stocks_needed": 8,
            "message": "Start by adding 8-10 different stocks for safety"
        }
    
    # Add new stock if provided
    portfolio = list(current_portfolio)
    if new_stock:
        portfolio.append(new_stock)
    
    # Get correlation matrix
    correlations = calculate_correlations(portfolio)
    
    # Calculate allocation (equal weight is safe for beginners)
    num_stocks = len(portfolio)
    allocation_per_stock = 100 / num_stocks
    
    allocation = {ticker: round(allocation_per_stock, 1) for ticker in portfolio}
    
    # Assess portfolio risk
    avg_correlation = calculate_average_correlation(correlations)
    risk_level = assess_risk_level(avg_correlation)
    
    # Find negatively correlated stocks to add for diversification
    negatively_correlated = find_negative_correlations(portfolio, correlations)
    
    recommendation = {
        "allocation": allocation,
        "allocation_message": f"Recommended: {allocation_per_stock:.1f}% per stock",
        "risk_level": risk_level,
        "avg_correlation": round(avg_correlation, 2),
        "diversification": negatively_correlated,
        "total_stocks_needed": 8,
        "max_per_stock": "Never put more than 10% in one stock",
        "minimum_stocks": f"You should have at least 8 stocks for safety",
        "tips": [
            "✅ Equal weight (each stock same %) is safest for beginners",
            "📊 Add more stocks from different sectors (tech, healthcare, energy, etc.)",
            "📉 Avoid buying all stocks that move together",
            "⏰ Rebalance every 3-6 months"
        ]
    }
    
    return recommendation


def calculate_correlations(tickers: List[str]) -> pd.DataFrame:
    """
    Calculate correlation between stocks in portfolio.
    Returns a correlation matrix (1 = move together, -1 = opposite, 0 = independent)
    """
    try:
        data = yf.download(tickers, period="1y", progress=False)["Adj Close"]
        returns = data.pct_change()
        return returns.corr()
    except Exception:
        return pd.DataFrame()


def calculate_average_correlation(corr_matrix: pd.DataFrame) -> float:
    """Calculate average correlation (excluding diagonal)."""
    if corr_matrix.empty:
        return 0
    
    # Get upper triangle of correlation matrix (excluding diagonal)
    n = len(corr_matrix)
    correlations = []
    for i in range(n):
        for j in range(i + 1, n):
            correlations.append(corr_matrix.iloc[i, j])
    
    return sum(correlations) / len(correlations) if correlations else 0


def assess_risk_level(avg_correlation: float) -> str:
    """
    Assess portfolio risk based on average correlation.
    Lower correlation = lower risk (stocks don't move together)
    """
    if avg_correlation < -0.2:
        return "🟢 VERY LOW RISK - Stocks move in opposite directions (Best diversification)"
    elif avg_correlation < 0.3:
        return "🟢 LOW RISK - Stocks move somewhat independently (Good diversification)"
    elif avg_correlation < 0.6:
        return "🟡 MEDIUM RISK - Stocks move somewhat together (Add more diversity)"
    else:
        return "🔴 HIGH RISK - Stocks move together (Too correlated, risky)"


def find_negative_correlations(portfolio: List[str], 
                                corr_matrix: pd.DataFrame,
                                suggestion_pool: List[str] = None) -> List[Dict]:
    """
    Find stocks with negative correlation to current portfolio.
    Negative correlation = prices move opposite = good for diversification.
    
    Parameters
    ----------
    portfolio : list
        Current portfolio tickers
    corr_matrix : pd.DataFrame
        Correlation matrix of portfolio
    suggestion_pool : list, optional
        Suggested tickers to check against
        
    Returns
    -------
    list of dicts with suggestion, correlation, and reason
    """
    
    if suggestion_pool is None:
        # Suggest different sectors/types
        suggestion_pool = [
            # Tech (if not in portfolio)
            "AAPL", "MSFT", "NVDA", "META", "GOOGL",
            # Healthcare
            "JNJ", "PFE", "UNH", "ABBV",
            # Utilities (defensive, less correlated)
            "NEE", "DUK", "SO", "XEL",
            # Consumer staples (defensive)
            "PG", "KO", "MCD", "WMT",
            # Energy (often negatively correlated to tech)
            "XOM", "CVX", "SLB",
            # Financials
            "JPM", "BAC", "GS", "MS",
            # Bonds/Interest (negatively correlated to stocks)
            "BND", "TLT"
        ]
    
    suggestions = []
    
    for candidate in suggestion_pool:
        if candidate in portfolio:
            continue
        
        # Try to calculate correlation with portfolio average
        try:
            # For simplicity, get average correlation to portfolio
            candidate_data = yf.download([candidate] + portfolio[:3], 
                                        period="1y", progress=False)["Adj Close"]
            candidate_corr = candidate_data[candidate].corr(candidate_data.drop(columns=candidate).mean(axis=1))
            
            if candidate_corr < -0.1:  # Negatively correlated
                sector = get_sector(candidate)
                suggestions.append({
                    "ticker": candidate,
                    "correlation": round(candidate_corr, 2),
                    "sector": sector,
                    "reason": f"Moves opposite to your stocks (correlation: {candidate_corr:.2f})",
                    "benefit": "Reduces portfolio risk"
                })
        except Exception:
            continue
    
    # Return top 3 suggestions sorted by most negative correlation
    return sorted(suggestions, key=lambda x: x["correlation"])[:3]


def get_sector(ticker: str) -> str:
    """Get rough sector classification for a ticker."""
    tech = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMD", "TSLA"]
    healthcare = ["JNJ", "PFE", "UNH", "ABBV", "LLY"]
    energy = ["XOM", "CVX", "SLB", "MPC"]
    utilities = ["NEE", "DUK", "SO", "XEL"]
    consumer = ["WMT", "PG", "KO", "MCD", "AMZN"]
    financials = ["JPM", "BAC", "GS", "MS"]
    
    if ticker in tech:
        return "Technology"
    elif ticker in healthcare:
        return "Healthcare"
    elif ticker in energy:
        return "Energy"
    elif ticker in utilities:
        return "Utilities"
    elif ticker in consumer:
        return "Consumer"
    elif ticker in financials:
        return "Financials"
    else:
        return "Other"


# ========== RISK/REWARD EXPLANATION ==========

def explain_risk_reward(current_price: float, 
                       target_price_high: float,
                       target_price_low: float) -> Dict[str, str]:
    """
    Explain potential gain/loss in simple terms.
    
    Parameters
    ----------
    current_price : float
        Current stock price
    target_price_high : float
        Optimistic target (upside)
    target_price_low : float
        Pessimistic target (downside)
        
    Returns
    -------
    dict with gain potential and risk explanation
    """
    
    potential_gain = ((target_price_high - current_price) / current_price) * 100
    potential_loss = ((target_price_low - current_price) / current_price) * 100
    risk_reward_ratio = potential_gain / abs(potential_loss) if potential_loss != 0 else 0
    
    return {
        "current_price": f"${current_price:.2f}",
        "upside_target": f"${target_price_high:.2f}",
        "downside_target": f"${target_price_low:.2f}",
        "potential_gain": f"💰 Could gain {potential_gain:.1f}%",
        "potential_loss": f"⚠️ Could lose {abs(potential_loss):.1f}%",
        "ratio": f"Risk/Reward: {risk_reward_ratio:.2f}:1",
        "assessment": "Good opportunity" if risk_reward_ratio > 1.5 else "Moderate opportunity" if risk_reward_ratio > 1 else "Poor opportunity"
    }


# ========== STOCK COMPARISON FOR BEGINNERS ==========

def compare_stocks(stock_analyses: Dict[str, Dict]) -> Dict:
    """
    Compare multiple stocks side-by-side for beginners.
    
    Parameters
    ----------
    stock_analyses : dict
        Dict mapping ticker -> analysis_data
        Example: {
            "AAPL": {...analysis...},
            "MSFT": {...analysis...},
            "NVDA": {...analysis...}
        }
        
    Returns
    -------
    dict with comparison table and recommendations
    """
    
    comparison = {
        "stocks": [],
        "winner": None,
        "summary": "",
        "tips": []
    }
    
    for ticker, analysis in stock_analyses.items():
        score = analysis.get("verdict", 0)
        verdict = get_verdict_with_emoji(score)
        
        stock_data = {
            "ticker": ticker,
            "score": score,
            "verdict_emoji": verdict["emoji"],
            "verdict": verdict["verdict"],
            "price": analysis.get("latest_price"),
            "momentum": analysis.get("factor", {}).get("momentum_score", 0),
            "sentiment": analysis.get("sentiment", {}).get("overall_sentiment", 0)
        }
        comparison["stocks"].append(stock_data)
    
    # Find winner (highest score)
    if comparison["stocks"]:
        winner = max(comparison["stocks"], key=lambda x: x["score"])
        comparison["winner"] = winner["ticker"]
        comparison["summary"] = f"🏆 {winner['ticker']} has the highest score ({winner['score']:.0f}) - Best opportunity"
        comparison["tips"] = [
            "📊 Higher score = Better buy signal, but check price first",
            "💰 Compare all three factors: Score, Price, and Risk",
            "⏰ Don't rush - wait for best entry point (Price to dip)",
            "🎯 You don't have to pick just one - can buy multiple stocks!"
        ]
    
    return comparison

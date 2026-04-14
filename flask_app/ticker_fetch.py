"""
Optimized ticker fetching: dedupes tickers, uses Polygon.io as primary, yfinance as fallback
"""
import time
from typing import List, Dict, Tuple, Optional
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

try:
    from flask_app.polygon_provider import fetch_eod_data, fetch_multiple_tickers, get_current_price, is_available as polygon_available
except ImportError:
    from polygon_provider import fetch_eod_data, fetch_multiple_tickers, get_current_price, is_available as polygon_available

try:
    from flask_app.yfinance_utils import yf_download_with_retry
except ImportError:
    from yfinance_utils import yf_download_with_retry

try:
    from flask_app.cache_utils import get_ticker_cache, set_ticker_cache, acquire_lock, release_lock
except ImportError:
    try:
        from cache_utils import get_ticker_cache, set_ticker_cache, acquire_lock, release_lock
    except ImportError:
        # Fallback: dummy cache functions
        def get_ticker_cache(*args, **kwargs): return None
        def set_ticker_cache(*args, **kwargs): pass
        def acquire_lock(*args, **kwargs): return str(time.time())
        def release_lock(*args, **kwargs): return True


def fetch_ticker_prices(tickers: List[str], period: str = "5d", logger=None) -> Dict[str, Dict]:
    """
    Fetch prices for multiple tickers with caching and deduplication.
    Uses Polygon.io as primary, falls back to yfinance if needed.
    Returns current price and % change (avoids quoteSummary).
    
    Args:
        tickers: List of ticker symbols
        period: yfinance period (e.g., "5d", "1d")
        logger: Optional logger
    
    Returns:
        Dict mapping ticker → {current_price, pct_change, timestamp}
    """
    # Dedupe and sort
    tickers = sorted(set([t.upper() for t in tickers if t]))
    if not tickers:
        return {}
    
    results = {}
    tickers_to_fetch = []
    
    # Check cache first
    for ticker in tickers:
        cached = get_ticker_cache(ticker, "price")
        if cached:
            if logger:
                logger.info(f"📦 [CACHE] {ticker} price")
            results[ticker] = cached
        else:
            tickers_to_fetch.append(ticker)
    
    if not tickers_to_fetch:
        return results
    
    # Fetch missing tickers in one batch
    if logger:
        logger.info(f"🔍 [FETCH] {tickers_to_fetch} - batch request")
    
    # Try Polygon.io first (primary), fall back to yfinance
    data = None
    
    if polygon_available():
        if logger:
            logger.info(f"🔷 Trying Polygon.io for {tickers_to_fetch}...")
        try:
            # Convert period to start_date
            now = datetime.now()
            if period == "5d":
                start_date = (now - timedelta(days=5)).strftime("%Y-%m-%d")
            elif period == "1d":
                start_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                # Default to 1 month
                start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            
            data = fetch_multiple_tickers(
                tickers_to_fetch,
                start_date=start_date,
                end_date=now.strftime("%Y-%m-%d"),
                logger=logger
            )
            
            if data is not None and not data.empty:
                if logger:
                    logger.info(f"✅ Polygon.io returned {len(data)} rows")
            else:
                if logger:
                    logger.warning(f"⚠️  Polygon.io returned no data, falling back to yfinance")
                data = None
        except Exception as e:
            if logger:
                logger.warning(f"⚠️  Polygon.io failed: {str(e)[:100]}, trying yfinance...")
            data = None
    
    # Fall back to yfinance if Polygon not available or failed
    if data is None or data.empty:
        if logger:
            logger.info(f"📊 Using yfinance as fallback for {tickers_to_fetch}...")
        try:
            data = yf_download_with_retry(
                tickers_to_fetch,
                period=period,
                progress=False,
                auto_adjust=True,
                logger=logger
            )
        except Exception as e:
            if logger:
                logger.error(f"❌ Both Polygon and yfinance failed: {str(e)[:100]}")
            return results
        
        if data.empty:
            if logger:
                logger.warning(f"⚠️  No data returned for {tickers_to_fetch}")
            return results
    
    # Parse results
    now = datetime.now()
    for ticker in tickers_to_fetch:
        try:
            if len(tickers_to_fetch) == 1:
                # Single ticker
                ticker_data = data
            else:
                # Multiple tickers
                ticker_data = data[ticker] if ticker in data.columns else None
            
            if ticker_data is not None and len(ticker_data) >= 2:
                # Get close prices (handle both yfinance and Polygon formats)
                if isinstance(ticker_data, pd.DataFrame):
                    if "close" in ticker_data.columns:
                        current_price = float(ticker_data["close"].iloc[-1])
                        prev_close = float(ticker_data["close"].iloc[-2])
                    elif "Close" in ticker_data.columns:
                        current_price = float(ticker_data["Close"].iloc[-1])
                        prev_close = float(ticker_data["Close"].iloc[-2])
                    else:
                        continue
                else:
                    # Series
                    current_price = float(ticker_data.iloc[-1])
                    prev_close = float(ticker_data.iloc[-2])
                
                pct_change = ((current_price - prev_close) / prev_close * 100) if prev_close != 0 else 0
                
                result = {
                    "current_price": current_price,
                    "pct_change": round(pct_change, 2),
                    "timestamp": now.isoformat(),
                    "period": period,
                }
                results[ticker] = result
                
                # Cache for 60 seconds
                set_ticker_cache(ticker, result, ttl=60, cache_type="price")
                
                if logger:
                    logger.info(f"✅ {ticker}: ${current_price:.2f} ({pct_change:+.2f}%)")
            else:
                if logger:
                    logger.warning(f"⚠️  Insufficient data for {ticker}")
        except Exception as e:
            if logger:
                logger.warning(f"❌ Error parsing {ticker}: {e}")
    
    return results


def fetch_tickers_combined(
    portfolio_tickers: List[str],
    watchlist_tickers: List[str],
    indices: List[str] = None,
    period: str = "5d",
    logger=None
) -> Tuple[Dict[str, Dict], Dict[str, Dict], Dict[str, Dict]]:
    """
    Fetch all tickers in one batch, then split results by category.
    Much more efficient than fetching portfolio, then watchlist, then indices separately.
    
    Returns:
        (portfolio_prices, watchlist_prices, indices_prices)
    """
    indices = indices or []
    
    # Combine all tickers into one fetch
    all_tickers = list(set(portfolio_tickers + watchlist_tickers + indices))
    all_prices = fetch_ticker_prices(all_tickers, period=period, logger=logger)
    
    # Split by category
    portfolio_prices = {t: all_prices[t] for t in portfolio_tickers if t in all_prices}
    watchlist_prices = {t: all_prices[t] for t in watchlist_tickers if t in all_prices}
    indices_prices = {t: all_prices[t] for t in indices if t in all_prices}
    
    return portfolio_prices, watchlist_prices, indices_prices

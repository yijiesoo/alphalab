"""
AlphaVantage stock data provider - replaces yfinance
Handles daily stock prices with caching and retry logic
"""
import os
import time
import pandas as pd
from datetime import datetime, timedelta
from alpha_vantage.timeseries import TimeSeries

# Initialize AlphaVantage client
API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "")
if not API_KEY:
    print("⚠️  ALPHAVANTAGE_API_KEY not set in environment")

try:
    ts = TimeSeries(key=API_KEY, output_format='pandas')
except Exception as e:
    print(f"⚠️  AlphaVantage initialization warning: {e}")
    ts = None

# Cache for ticker data
_cache = {}
_cache_timestamps = {}
CACHE_DURATION = 300  # 5 minutes


def get_stock_data(ticker: str, period: str = "5d", retry: int = 3) -> pd.DataFrame:
    """
    Get daily stock data from AlphaVantage.
    
    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        period: Period (only "1d", "5d" supported - returns daily data)
        retry: Number of retries
    
    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    if not ts:
        print(f"❌ AlphaVantage not initialized")
        return pd.DataFrame()
    
    ticker = ticker.upper()
    
    # Check cache
    now = time.time()
    cache_key = f"{ticker}:{period}"
    if cache_key in _cache and (now - _cache_timestamps.get(cache_key, 0)) < CACHE_DURATION:
        print(f"📦 [CACHE HIT] {ticker}")
        return _cache[cache_key]
    
    # Fetch from API with retries
    for attempt in range(retry):
        try:
            print(f"🔍 [API CALL] AlphaVantage {ticker} (attempt {attempt+1}/{retry})")
            
            # AlphaVantage returns data with date as index
            data, meta = ts.get_daily(symbol=ticker, outputsize='full')
            
            if data.empty:
                print(f"⚠️  No data for {ticker} (attempt {attempt+1}/{retry})")
                if attempt < retry - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue
            
            # Sort by date (most recent first)
            data = data.sort_index(ascending=False)
            
            # Cache the result
            _cache[cache_key] = data
            _cache_timestamps[cache_key] = now
            
            print(f"✅ [SUCCESS] {ticker} - {len(data)} days of data")
            return data
            
        except Exception as e:
            print(f"❌ [FAILED] {ticker} (attempt {attempt+1}/{retry}): {str(e)[:100]}")
            if attempt < retry - 1:
                wait_time = 2 ** attempt
                print(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
    
    print(f"💥 [GIVE UP] {ticker} failed after {retry} attempts")
    return pd.DataFrame()


def get_current_price(ticker: str) -> dict:
    """
    Get current price and % change for a ticker.
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        Dict with {current_price, pct_change, timestamp}
    """
    data = get_stock_data(ticker)
    
    if data.empty or len(data) < 2:
        return {"current_price": 0, "pct_change": 0, "timestamp": datetime.now().isoformat()}
    
    try:
        # Get latest close and previous close
        latest = data.iloc[0]
        prev = data.iloc[1]
        
        current_price = float(latest['4. close'])
        prev_close = float(prev['4. close'])
        pct_change = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
        
        return {
            "current_price": current_price,
            "pct_change": pct_change,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ Error parsing {ticker} data: {e}")
        return {"current_price": 0, "pct_change": 0, "timestamp": datetime.now().isoformat()}


def batch_get_prices(tickers: list) -> dict:
    """
    Get prices for multiple tickers efficiently.
    
    Args:
        tickers: List of ticker symbols
    
    Returns:
        Dict mapping ticker → {current_price, pct_change, timestamp}
    """
    results = {}
    
    # Dedupe tickers
    tickers = sorted(set([t.upper() for t in tickers if t]))
    
    for ticker in tickers:
        results[ticker] = get_current_price(ticker)
        # AlphaVantage has rate limits, be respectful
        time.sleep(0.3)
    
    return results

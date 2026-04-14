"""
Polygon.io data provider - replaces yfinance
Fetches EOD (End-of-Day) stock data from Polygon.io
"""
import os
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import requests

# Polygon.io API client
from polygon import RESTClient

# Initialize Polygon client
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
if not POLYGON_API_KEY:
    print("⚠️  POLYGON_API_KEY not set in environment - Polygon.io disabled")
    POLYGON_CLIENT = None
else:
    POLYGON_CLIENT = RESTClient(api_key=POLYGON_API_KEY)
    print("✅ Polygon.io client initialized")


def fetch_eod_data(
    ticker: str,
    start_date: str,
    end_date: Optional[str] = None,
    logger=None,
) -> Optional[pd.DataFrame]:
    """
    Fetch End-of-Day (EOD) data for a single ticker from Polygon.io
    
    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        start_date: ISO format start date (e.g., "2015-01-01")
        end_date: ISO format end date (defaults to today)
        logger: Optional logger for debug output
    
    Returns:
        DataFrame with columns [timestamp, open, high, low, close, volume]
        or None if data unavailable
    """
    if not POLYGON_CLIENT:
        print(f"⚠️  Polygon.io not configured - skipping {ticker}")
        return None
    
    try:
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        msg = f"🔍 Fetching {ticker} ({start_date} to {end_date}) from Polygon.io"
        if logger:
            logger.info(msg)
        else:
            print(msg)
        
        # Fetch aggregates from Polygon
        aggs = []
        for agg in POLYGON_CLIENT.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            start=start_date,
            end=end_date,
            sort="asc",
            limit=50000,  # Max results per request
        ):
            aggs.append({
                "timestamp": pd.Timestamp(agg.timestamp, unit="ms"),
                "open": agg.open,
                "high": agg.high,
                "low": agg.low,
                "close": agg.close,
                "volume": agg.volume,
            })
        
        if not aggs:
            msg = f"⚠️  No data returned for {ticker}"
            if logger:
                logger.warning(msg)
            else:
                print(msg)
            return None
        
        df = pd.DataFrame(aggs)
        df.set_index("timestamp", inplace=True)
        df.index.name = "Date"
        
        msg = f"✅ {ticker}: {len(df)} days of data"
        if logger:
            logger.info(msg)
        else:
            print(msg)
        
        return df
    
    except Exception as e:
        msg = f"❌ Error fetching {ticker}: {str(e)[:100]}"
        if logger:
            logger.error(msg)
        else:
            print(msg)
        return None


def fetch_multiple_tickers(
    tickers: List[str],
    start_date: str,
    end_date: Optional[str] = None,
    logger=None,
) -> pd.DataFrame:
    """
    Fetch data for multiple tickers and combine into a single DataFrame
    (compatible with yfinance API)
    
    Args:
        tickers: List of ticker symbols
        start_date: ISO format start date
        end_date: ISO format end date
        logger: Optional logger
    
    Returns:
        DataFrame with columns = tickers, rows = dates, values = adjusted close
    """
    if not POLYGON_CLIENT:
        print("⚠️  Polygon.io not configured")
        return pd.DataFrame()
    
    results = {}
    
    for ticker in tickers:
        df = fetch_eod_data(ticker, start_date, end_date, logger)
        if df is not None and not df.empty:
            results[ticker] = df["close"]
        else:
            # Return NaN for missing tickers (consistent with yfinance)
            results[ticker] = pd.Series(dtype=float)
    
    if not results:
        return pd.DataFrame()
    
    # Combine all tickers into one DataFrame
    combined = pd.DataFrame(results)
    combined.index.name = "Date"
    
    msg = f"✅ Combined data: {len(combined)} dates, {len(combined.columns)} tickers"
    if logger:
        logger.info(msg)
    else:
        print(msg)
    
    return combined


def get_current_price(
    ticker: str,
    logger=None,
) -> Optional[float]:
    """
    Get the most recent close price for a ticker
    
    Args:
        ticker: Stock ticker symbol
        logger: Optional logger
    
    Returns:
        Current close price or None if unavailable
    """
    if not POLYGON_CLIENT:
        return None
    
    try:
        # Get previous business day's quote
        quote = POLYGON_CLIENT.get_previous_close(
            ticker=ticker,
            adjusted=True,
        )
        
        if quote.results:
            price = quote.results[0].close
            msg = f"✅ {ticker} current price: ${price:.2f}"
            if logger:
                logger.info(msg)
            else:
                print(msg)
            return float(price)
        
        return None
    
    except Exception as e:
        msg = f"⚠️  Could not get current price for {ticker}: {str(e)[:100]}"
        if logger:
            logger.warning(msg)
        else:
            print(msg)
        return None


def is_available() -> bool:
    """Check if Polygon.io is properly configured"""
    return POLYGON_CLIENT is not None

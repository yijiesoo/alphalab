"""
yfinance utilities with caching, retry logic, and request tracking
"""
import time
import pandas as pd
import yfinance as yf

# Cache for ticker data
_ticker_cache = {}
_cache_timestamps = {}
CACHE_DURATION = 300  # 5 minutes

# Request metrics tracking
_request_metrics = {
    "api_calls": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "rate_limits": 0,
    "last_reset": time.time(),
}


def get_request_stats():
    """Get current request statistics and reset if over 1 hour old"""
    global _request_metrics
    now = time.time()
    if now - _request_metrics["last_reset"] > 3600:  # Reset every hour
        stats = _request_metrics.copy()
        _request_metrics = {
            "api_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "rate_limits": 0,
            "last_reset": now,
        }
        return stats
    return _request_metrics


def yf_download_with_retry(tickers, max_retries: int = 3, logger=None, **kwargs):
    """
    Wrapper around yf.download with exponential back-off retry logic.

    yfinance scrapes Yahoo Finance and can receive HTTP 429 (Too Many Requests)
    under concurrent or rapid usage. This wrapper retries up to *max_retries*
    times with a short sleep between attempts so callers get a result even when
    one attempt is rate-limited.
    
    Args:
        tickers: str or list of ticker symbols
        max_retries: number of retry attempts
        logger: optional logger for detailed output
        **kwargs: passed to yf.download (period, progress, auto_adjust, etc)
    
    Returns:
        pandas DataFrame with ticker data, or empty DataFrame on failure
    """
    global _request_metrics
    
    # Prepare logging info
    ticker_str = str(tickers)
    period = kwargs.get('period', 'unknown')
    
    def log_msg(msg):
        if logger:
            logger.info(msg)
        else:
            print(msg)
    
    # Check cache first to reduce API calls
    cache_key = str(sorted(tickers if isinstance(tickers, list) else [tickers]) + list(kwargs.items()))
    now = time.time()
    if cache_key in _ticker_cache and (now - _cache_timestamps.get(cache_key, 0)) < CACHE_DURATION:
        _request_metrics["cache_hits"] += 1
        log_msg(f"📦 [CACHE HIT] {ticker_str} (period={period})")
        return _ticker_cache[cache_key]
    
    _request_metrics["cache_misses"] += 1
    _request_metrics["api_calls"] += 1
    log_msg(f"🔍 [API CALL] Fetching {ticker_str} (period={period}) - API calls this hour: {_request_metrics['api_calls']}")
    
    for attempt in range(max_retries):
        try:
            data = yf.download(tickers, **kwargs)
            if not data.empty:
                # Cache the result
                _ticker_cache[cache_key] = data
                _cache_timestamps[cache_key] = now
                rows = len(data)
                log_msg(f"✅ [SUCCESS] {ticker_str} (period={period}, rows={rows}, attempt={attempt+1}/{max_retries})")
                return data
            else:
                log_msg(f"⚠️  [EMPTY DATA] {ticker_str} (period={period}, attempt={attempt+1}/{max_retries})")
        except Exception as exc:
            exc_type = type(exc).__name__
            # Extract HTTP status code if available
            status_code = ""
            if "429" in str(exc):
                status_code = " [429 RATE LIMITED]"
                _request_metrics["rate_limits"] += 1
            elif "403" in str(exc):
                status_code = " [403 FORBIDDEN]"
            elif "401" in str(exc):
                status_code = " [401 UNAUTHORIZED]"
            
            log_msg(f"❌ [FAILED] {ticker_str} (period={period}, attempt={attempt+1}/{max_retries}){status_code} - {exc_type}: {str(exc)[:100]}")
        
        if attempt < max_retries - 1:
            backoff = 1.5 * (attempt + 1)
            log_msg(f"⏳ [RETRY BACKOFF] Waiting {backoff}s before retry...")
            time.sleep(backoff)
    
    # Return empty DataFrame on persistent failure
    log_msg(f"💥 [GIVE UP] {ticker_str} failed after {max_retries} attempts")
    return pd.DataFrame()

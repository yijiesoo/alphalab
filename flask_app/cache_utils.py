"""
Redis-based caching with distributed locking for yfinance data.
Reduces request bursts and rate limiting.
"""
import os
import json
import time
from typing import Optional, Dict, Any
import redis
from urllib.parse import urlparse

# Initialize Redis connection (gracefully handle if not available)
REDIS_URL = os.getenv("REDIS_URL")
print(f"🔧 REDIS_URL from env: {REDIS_URL[:40] if REDIS_URL else 'Not set'}...")

try:
    if REDIS_URL:
        # Parse the URL to handle Railway's internal DNS issues
        parsed = urlparse(REDIS_URL)
        
        # Use environment variables for host/port if available (more reliable on Railway)
        redis_host = os.getenv("REDISHOST", parsed.hostname or "localhost")
        redis_port = int(os.getenv("REDISPORT", parsed.port or 6379))
        redis_password = os.getenv("REDISPASSWORD", parsed.password or "")
        
        print(f"🔧 Connecting to Redis: {redis_host}:{redis_port} (auth={bool(redis_password)})")
        
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password if redis_password else None,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True
        )
        redis_client.ping()
        REDIS_AVAILABLE = True
        print("✅ Redis connected successfully")
    else:
        raise ValueError("REDIS_URL not set in environment")
except Exception as e:
    print(f"⚠️  Redis not available: {e}. Caching disabled (will still batch fetch).")
    redis_client = None
    REDIS_AVAILABLE = False


def get_ticker_cache(ticker: str, cache_type: str = "price") -> Optional[Dict[str, Any]]:
    """
    Get cached ticker data.
    
    Args:
        ticker: Stock ticker symbol
        cache_type: "price" for intraday price, "info" for company info
    
    Returns:
        Cached data dict or None if not in cache or expired
    """
    if not REDIS_AVAILABLE:
        return None
    
    try:
        key = f"ticker:{cache_type}:{ticker}"
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        print(f"⚠️  Cache get error: {e}")
    
    return None


def set_ticker_cache(ticker: str, data: Dict[str, Any], ttl: int = 60, cache_type: str = "price"):
    """
    Set cached ticker data.
    
    Args:
        ticker: Stock ticker symbol
        data: Data to cache
        ttl: Time to live in seconds
        cache_type: "price" or "info"
    """
    if not REDIS_AVAILABLE:
        return
    
    try:
        key = f"ticker:{cache_type}:{ticker}"
        redis_client.setex(key, ttl, json.dumps(data))
    except Exception as e:
        print(f"⚠️  Cache set error: {e}")


def acquire_lock(lock_key: str, ttl: int = 10) -> Optional[str]:
    """
    Try to acquire a distributed lock using Redis.
    Returns a lock token if successful, None otherwise.
    
    Args:
        lock_key: Unique key for the lock (e.g., "fetch:AAPL:price")
        ttl: Lock timeout in seconds
    
    Returns:
        Lock token (unique ID) if acquired, None if someone else has it
    """
    if not REDIS_AVAILABLE:
        return None
    
    try:
        lock_token = str(time.time())
        acquired = redis_client.set(
            lock_key,
            lock_token,
            nx=True,  # Only set if not exists
            ex=ttl  # Expire after ttl seconds
        )
        return lock_token if acquired else None
    except Exception as e:
        print(f"⚠️  Lock acquire error: {e}")
    
    return None


def release_lock(lock_key: str, lock_token: str) -> bool:
    """
    Release a distributed lock (only if we still own it).
    
    Args:
        lock_key: The lock key
        lock_token: The token we received when acquiring the lock
    
    Returns:
        True if released, False otherwise
    """
    if not REDIS_AVAILABLE:
        return True
    
    try:
        # Only delete if we still own it (token matches)
        current = redis_client.get(lock_key)
        if current == lock_token:
            redis_client.delete(lock_key)
            return True
    except Exception as e:
        print(f"⚠️  Lock release error: {e}")
    
    return False


def cache_and_lock_pattern(
    key: str,
    fetch_fn,
    ttl: int = 60,
    lock_ttl: int = 10,
    stale_ttl: int = 300
):
    """
    Cache-with-lock pattern: serve stale data while refreshing in background.
    
    Args:
        key: Cache key (e.g., "ticker:price:AAPL")
        fetch_fn: Function to call to fetch fresh data
        ttl: Fresh cache TTL (seconds)
        lock_ttl: How long to hold the lock (seconds)
        stale_ttl: How long stale data is acceptable (seconds)
    
    Returns:
        Fresh or cached data
    """
    # Try to get fresh cache
    cached = redis_client.get(f"{key}:data") if REDIS_AVAILABLE else None
    if cached:
        return json.loads(cached)
    
    # Try to acquire lock
    lock_key = f"{key}:lock"
    lock_token = acquire_lock(lock_key, lock_ttl) if REDIS_AVAILABLE else str(time.time())
    
    if lock_token:
        # We got the lock - fetch fresh data
        try:
            data = fetch_fn()
            if REDIS_AVAILABLE:
                redis_client.setex(
                    f"{key}:data",
                    ttl,
                    json.dumps(data)
                )
                release_lock(lock_key, lock_token)
            return data
        except Exception as e:
            print(f"❌ Fetch error: {e}")
            if REDIS_AVAILABLE:
                release_lock(lock_key, lock_token)
            # Return stale data if available
            if REDIS_AVAILABLE:
                stale = redis_client.get(f"{key}:stale")
                return json.loads(stale) if stale else None
            return None
    else:
        # Someone else has the lock - return stale data if available
        if REDIS_AVAILABLE:
            stale = redis_client.get(f"{key}:stale")
            if stale:
                return json.loads(stale)
        
        # No stale data either - wait a bit and retry once
        time.sleep(0.5)
        if REDIS_AVAILABLE:
            fresh = redis_client.get(f"{key}:data")
            if fresh:
                return json.loads(fresh)
        
        return None

"""
Supabase database service
"""
import traceback

from ..config import Config

# Global supabase instance
_supabase = None


def init_supabase():
    """Initialize Supabase client"""
    global _supabase
    try:
        from supabase import create_client
        if Config.SUPABASE_URL and Config.SUPABASE_KEY:
            _supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
            print("✅ Supabase initialized")
            return _supabase
        else:
            print("⚠️  Supabase credentials not found")
            return None
    except ImportError:
        print("⚠️  Supabase not available")
        return None


def get_supabase():
    """Get Supabase instance"""
    global _supabase
    if _supabase is None:
        _supabase = init_supabase()
    return _supabase


def sync_user_to_supabase(email: str, firebase_uid: str, is_new: bool = False) -> bool:
    """Sync user to Supabase users table. Returns True on success."""
    sb = get_supabase()
    if not sb:
        return False

    try:
        if is_new:
            sb.table("users").insert({
                "email": email,
                "firebase_uid": firebase_uid,
            }).execute()
            print(f"✅ New user created in Supabase: {email}")
        else:
            sb.table("users").upsert({
                "email": email,
                "firebase_uid": firebase_uid,
            }).execute()
            print(f"✅ User synced in Supabase: {email}")
        return True
    except Exception as e:
        print(f"⚠️  Could not sync user to Supabase: {e}")
        print(traceback.format_exc())
        return False


def get_user_watchlist(email: str) -> list:
    """Get user's watchlist tickers from Supabase.

    Uses the 'watchlist' table where each user has one row with a 'tickers' array.
    Returns a flat list of ticker strings.
    """
    sb = get_supabase()
    if not sb:
        return []

    try:
        response = sb.table("watchlist").select("tickers").eq("email", email).execute()
        if response.data and len(response.data) > 0:
            return response.data[0].get("tickers") or []
        return []
    except Exception as e:
        print(f"❌ Error getting watchlist: {e}")
        print(traceback.format_exc())
        return []


def add_to_watchlist(email: str, ticker: str) -> bool:
    """Add ticker to user's watchlist. Returns True on success."""
    sb = get_supabase()
    if not sb:
        return False

    try:
        ticker = ticker.upper()
        response = sb.table("watchlist").select("id, tickers").eq("email", email).execute()

        if response.data and len(response.data) > 0:
            row = response.data[0]
            tickers = row.get("tickers") or []
            if ticker in tickers:
                return True  # already present
            tickers.append(ticker)
            sb.table("watchlist").update({"tickers": tickers}).eq("id", row["id"]).execute()
        else:
            sb.table("watchlist").insert({
                "email": email,
                "tickers": [ticker],
            }).execute()
        return True
    except Exception as e:
        print(f"❌ Error adding to watchlist: {e}")
        print(traceback.format_exc())
        return False


def remove_from_watchlist(email: str, ticker: str) -> bool:
    """Remove ticker from user's watchlist. Returns True on success."""
    sb = get_supabase()
    if not sb:
        return False

    try:
        ticker = ticker.upper()
        response = sb.table("watchlist").select("id, tickers").eq("email", email).execute()

        if response.data and len(response.data) > 0:
            row = response.data[0]
            tickers = [t for t in (row.get("tickers") or []) if t != ticker]
            sb.table("watchlist").update({"tickers": tickers}).eq("id", row["id"]).execute()
        return True
    except Exception as e:
        print(f"❌ Error removing from watchlist: {e}")
        print(traceback.format_exc())
        return False

"""
Supabase database service
"""
import os
from config import Config

# Global supabase instance
_supabase = None


def init_supabase():
    """Initialize Supabase client"""
    global _supabase
    try:
        from supabase import create_client, Client
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


def sync_user_to_supabase(email: str, firebase_uid: str, is_new: bool = False):
    """Sync user to Supabase users table"""
    sb = get_supabase()
    if not sb:
        return
    
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
    except Exception as e:
        print(f"⚠️  Could not sync user to Supabase: {e}")


def get_user_watchlist(email: str):
    """Get user's watchlist from Supabase"""
    sb = get_supabase()
    if not sb:
        return []
    
    try:
        response = sb.table("watchlist").select("ticker").eq("email", email).execute()
        return [item.get("ticker") for item in response.data] if response.data else []
    except Exception as e:
        print(f"❌ Error getting watchlist: {e}")
        return []


def add_to_watchlist(email: str, ticker: str):
    """Add ticker to user's watchlist"""
    sb = get_supabase()
    if not sb:
        return False
    
    try:
        sb.table("watchlist").insert({
            "email": email,
            "ticker": ticker.upper(),
        }).execute()
        return True
    except Exception as e:
        print(f"❌ Error adding to watchlist: {e}")
        return False


def remove_from_watchlist(email: str, ticker: str):
    """Remove ticker from user's watchlist"""
    sb = get_supabase()
    if not sb:
        return False
    
    try:
        sb.table("watchlist").delete().eq("email", email).eq("ticker", ticker.upper()).execute()
        return True
    except Exception as e:
        print(f"❌ Error removing from watchlist: {e}")
        return False

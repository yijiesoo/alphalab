"""
Supabase database service module
"""
try:
    from flask_app.services import get_supabase, sync_user_to_supabase
except ImportError:
    from services import get_supabase, sync_user_to_supabase

__all__ = ['get_supabase', 'sync_user_to_supabase']

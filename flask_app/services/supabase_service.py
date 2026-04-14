"""
Supabase database service module
This file is kept for backwards compatibility.
Import from flask_app.services instead:
  from flask_app.services import get_supabase, sync_user_to_supabase
"""

# Re-export from __init__.py
from flask_app.services import get_supabase, sync_user_to_supabase

__all__ = ['get_supabase', 'sync_user_to_supabase']

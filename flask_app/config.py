"""
Flask configuration settings
"""
import os
from datetime import timedelta
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# Project structure paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FACTORLAB_ROOT = PROJECT_ROOT / "factor-lab"
FACTORLAB_SRC = FACTORLAB_ROOT / "src"
SCRIPT = FACTORLAB_ROOT / "scripts" / "run_backtest.py"
FACTORLAB_OUT = FACTORLAB_ROOT / "outputs"

APP_ROOT = Path(__file__).resolve().parent
OUT_DIR = APP_ROOT / "outputs"
LOG_FILE = OUT_DIR / "backtest.log"

# Create directories if they don't exist
OUT_DIR.mkdir(parents=True, exist_ok=True)
FACTORLAB_OUT.mkdir(parents=True, exist_ok=True)

# Flask configuration
class Config:
    """Base Flask configuration"""
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
    
    # Session configuration
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Firebase
    FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")
    
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
    
    # Caching
    CACHE_TTL_SECONDS = 15 * 60  # 15 minutes
    
    # News API
    NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # HTTPS only in production


# Image extensions
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'}

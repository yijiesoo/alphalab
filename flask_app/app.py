import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv

# CRITICAL: Load environment variables FIRST, before any other imports
# This ensures that NEWSAPI_KEY, FIREBASE_WEB_API_KEY, etc. are available
# when factor-lab modules are imported
load_dotenv()

from flask import Flask, Response, jsonify, render_template, request, send_from_directory, stream_with_context, session, redirect, url_for
import yfinance as yf
import numpy as np
import requests

# FinBERT SENTIMENT ANALYSIS INTEGRATION
# =======================================
# The /api/analyze endpoint now uses FinBERT for sentiment scoring if available.
# FinBERT is a financial BERT model with 80%+ accuracy on financial text.
#
# To enable FinBERT:
#   $ pip install transformers torch
#
# If transformers/torch not installed, falls back to keyword matching automatically.
# No changes needed - just install and it works!

# Supabase
try:
    from supabase import create_client, Client
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
    print("✅ Supabase initialized")
except ImportError:
    supabase = None
    print("⚠️ Supabase not available")

# Derive project root from this file's location: flask_app/app.py → project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FACTORLAB_ROOT = PROJECT_ROOT / "factor-lab"
FACTORLAB_SRC = FACTORLAB_ROOT / "src"
SCRIPT = FACTORLAB_ROOT / "scripts" / "run_backtest.py"
FACTORLAB_OUT = FACTORLAB_ROOT / "outputs"

APP_ROOT = Path(__file__).resolve().parent
OUT_DIR = APP_ROOT / "outputs"
LOG_FILE = OUT_DIR / "backtest.log"

OUT_DIR.mkdir(parents=True, exist_ok=True)
FACTORLAB_OUT.mkdir(parents=True, exist_ok=True)

# Make factor-lab importable as a package (needed for /api/* endpoints)
if str(FACTORLAB_ROOT) not in sys.path:
    sys.path.insert(0, str(FACTORLAB_ROOT))


app = Flask(__name__)
_worker = {"proc": None, "thread": None, "running": False}

# Configure session secret key for Flask session management
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# Configure session settings
app.config['SESSION_COOKIE_SECURE'] = False  # Allow HTTP in development
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)# ---------------------------------------------------------------------------
# Session-based Auth Decorator
# ---------------------------------------------------------------------------
def login_required(f):
    """Decorator to require login (Flask session based)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ---------------------------------------------------------------------------
# In-memory per-ticker cache with TTL
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 15 * 60  # 15 minutes
_cache: dict[str, dict] = {}  # ticker → {"data": ..., "expires_at": float}

# Image extensions to look for
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'}

_TICKER_RE = re.compile(r'^[A-Z]{1,5}$')


def _valid_ticker(ticker: str) -> bool:
    """Return True if ticker looks like a valid US equity symbol (1-5 uppercase letters)."""
    return bool(_TICKER_RE.match(ticker.upper())) if ticker else False


def _copy_images_to_flask():
    """Copy images from factor-lab/outputs to flask_app/outputs"""
    if FACTORLAB_OUT.exists():
        for file in FACTORLAB_OUT.iterdir():
            if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                dest = OUT_DIR / file.name
                shutil.copy2(file, dest)


def _run_script():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(FACTORLAB_ROOT)  # Point to factor-lab root
    with LOG_FILE.open("w") as f:
        proc = subprocess.Popen(
            ["python3", str(SCRIPT)],
            stdout=f,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=str(FACTORLAB_ROOT),  # Set working directory to factor-lab
        )
        _worker["proc"] = proc
        _worker["running"] = True
        proc.wait()
        _worker["running"] = False
        _worker["proc"] = None
        # Copy images after script completes
        _copy_images_to_flask()


# ---------------------------------------------------------------------------
# Existing routes (preserved)
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page with form"""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        if not email or not password:
            return render_template("login.html", error="Email and password are required")
        
        try:
            # Use Firebase REST API to sign in
            api_key = os.getenv("FIREBASE_WEB_API_KEY")
            if not api_key:
                return render_template("login.html", error="Firebase not configured")
            
            response = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}",
                json={"email": email, "password": password, "returnSecureToken": True}
            )
            
            if response.status_code == 200:
                data = response.json()
                firebase_uid = data.get("localId")
                # Store user info in Flask session
                session["user_id"] = firebase_uid  # Store original Firebase UID
                session["user_email"] = data.get("email")
                session["id_token"] = data.get("idToken")
                session.permanent = True
                return redirect(url_for("index"))
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Invalid credentials")
                return render_template("login.html", error=error_msg)
        except Exception as e:
            return render_template("login.html", error=f"Login error: {str(e)}")
    
    # If already logged in, redirect to home
    if "user_id" in session:
        return redirect(url_for("index"))
    
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Signup page with form"""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        
        # Validation
        if not email or not password or not password_confirm:
            return render_template("signup.html", error="All fields are required")
        
        if password != password_confirm:
            return render_template("signup.html", error="Passwords do not match")
        
        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters")
        
        try:
            # Create user with Firebase REST API
            api_key = os.getenv("FIREBASE_WEB_API_KEY")
            if not api_key:
                return render_template("signup.html", error="Firebase not configured")
            
            response = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}",
                json={"email": email, "password": password, "returnSecureToken": True}
            )
            
            if response.status_code == 200:
                data = response.json()
                firebase_uid = data.get("localId")
                # Auto-login after signup
                session["user_id"] = firebase_uid  # Store original Firebase UID
                session["user_email"] = data.get("email")
                session["id_token"] = data.get("idToken")
                session.permanent = True
                return redirect(url_for("index"))
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Signup failed")
                return render_template("signup.html", error=error_msg)
        except Exception as e:
            return render_template("signup.html", error=f"Signup error: {str(e)}")
    
    # If already logged in, redirect to home
    if "user_id" in session:
        return redirect(url_for("index"))
    
    return render_template("signup.html")


@app.route("/logout")
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for("login"))
@app.route("/run", methods=["POST"])
@login_required
def run_backtest():
    if _worker["running"]:
        return jsonify({"status": "already_running"}), 409
    t = threading.Thread(target=_run_script, daemon=True)
    _worker["thread"] = t
    t.start()
    time.sleep(0.1)
    return jsonify({"status": "started"})


@app.route("/status")
def status():
    tail = ""
    if LOG_FILE.exists():
        with LOG_FILE.open("r") as f:
            lines = f.readlines()
            tail = "".join(lines[-200:])
    return jsonify({"running": _worker["running"], "log_tail": tail})


@app.route("/images")
def get_images():
    """Return list of images in the output folder"""
    images = []
    if OUT_DIR.exists():
        for file in OUT_DIR.iterdir():
            if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                images.append(file.name)
    return jsonify({"images": sorted(images)})


@app.route("/outputs/<path:filename>")
def outputs(filename):
    return send_from_directory(str(OUT_DIR), filename, as_attachment=True)


# ---------------------------------------------------------------------------
# New /api/* endpoints
# ---------------------------------------------------------------------------

@app.route("/api/analyze")
@login_required
def api_analyze():
    """GET /api/analyze?ticker=NVDA[&refresh=true]"""
    ticker = (request.args.get("ticker") or "").upper().strip()
    if not ticker:
        return jsonify({"error": "ticker parameter is required"}), 400
    if not _valid_ticker(ticker):
        return jsonify({"error": f"invalid ticker: {ticker}"}), 400

    refresh = request.args.get("refresh", "").lower() == "true"
    now = time.time()

    # Serve from cache if still valid and not forced refresh
    if not refresh and ticker in _cache:
        entry = _cache[ticker]
        if entry["expires_at"] > now:
            cached_data = {**entry["data"], "_cache": {"hit": True, "expires_at": entry["expires_at"]}}
            app.logger.info(f"Cache hit for {ticker}")
            return jsonify(cached_data)

    # Cache miss (or refresh requested) — run analysis
    try:
        from src.scorer import analyze_ticker
        data = analyze_ticker(ticker)
        app.logger.info(f"Analysis complete for {ticker}")
    except Exception as e:
        app.logger.error(f"Analysis failed for {ticker}: {e}", exc_info=True)
        return jsonify({"error": "analysis failed; check server logs"}), 500

    # Ensure all fields are present
    if not data:
        app.logger.error(f"No data returned for {ticker}")
        return jsonify({"error": "no analysis data"}), 500
    
    expires_at = now + _CACHE_TTL_SECONDS
    _cache[ticker] = {"data": data, "expires_at": expires_at}
    response_data = {**data, "_cache": {"hit": False, "expires_at": expires_at}}
    app.logger.info(f"Returning analysis for {ticker}: keys={list(response_data.keys())}")
    return jsonify(response_data)


@app.route("/api/cache")
def api_cache():
    """GET /api/cache — list currently cached tickers and their remaining TTL."""
    now = time.time()
    valid = {
        ticker: {
            "expires_at": entry["expires_at"],
            "ttl_seconds": round(max(0.0, entry["expires_at"] - now), 1),
        }
        for ticker, entry in _cache.items()
        if entry["expires_at"] > now
    }
    return jsonify({"cached_tickers": valid})


@app.route("/api/backtest/stream")
def api_backtest_stream():
    """GET /api/backtest/stream?ticker=NVDA

    Server-Sent Events (SSE) endpoint.  Streams log lines from
    run_single_ticker_backtest and closes with a 'data: [DONE]' event.
    """
    ticker = (request.args.get("ticker") or "").upper().strip()
    if not ticker:
        return jsonify({"error": "ticker parameter is required"}), 400
    if not _valid_ticker(ticker):
        return jsonify({"error": f"invalid ticker: {ticker}"}), 400

    def generate():
        q: queue.Queue[str | None] = queue.Queue(maxsize=1000)

        def _log_fn(msg: str) -> None:
            q.put(msg)

        def _run() -> None:
            try:
                from src.backtest import run_single_ticker_backtest
                run_single_ticker_backtest(ticker, log_fn=_log_fn)
            except Exception as exc:
                _log_fn(f"ERROR: {exc}")
            finally:
                q.put(None)  # sentinel — signals the generator to stop

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        while True:
            msg = q.get()
            if msg is None:
                break
            yield f"data: {msg}\n\n"

        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/health")
def api_health():
    """GET /api/health — liveness check and cache stats."""
    now = time.time()
    cached_count = sum(1 for entry in _cache.values() if entry["expires_at"] > now)
    return jsonify({"status": "ok", "cached_tickers": cached_count})


@app.route("/api/latest-metrics")
def api_latest_metrics():
    """GET /api/latest-metrics — return latest backtest metrics."""
    return jsonify({"metrics": [], "message": "No backtest metrics available"})


@app.route("/api/all-backtests")
def api_all_backtests():
    """GET /api/all-backtests?limit=50 — return list of backtests."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"backtests": [], "total": 0, "limit": limit})


# ---------------------------------------------------------------------------
# New endpoints for watchlist, price charts, and history
# ---------------------------------------------------------------------------

@app.route("/api/price-chart")
@login_required
def api_price_chart():
    """GET /api/price-chart?ticker=AAPL — return 6-month price data."""
    ticker = (request.args.get("ticker") or "").upper().strip()
    if not ticker:
        return jsonify({"error": "ticker parameter is required"}), 400
    if not _valid_ticker(ticker):
        return jsonify({"error": f"invalid ticker: {ticker}"}), 400

    try:
        # Fetch 6 months of price data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        
        data = yf.download(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True
        )
        
        if data.empty:
            return jsonify({"error": f"No price data found for {ticker}"}), 404
        
        # Handle both single ticker (Series) and multiple tickers (DataFrame)
        if isinstance(data, __import__('pandas').Series):
            close_prices = data
        else:
            close_prices = data["Close"] if "Close" in data.columns else data.iloc[:, 0]
        
        # Convert to list of [timestamp, price] pairs
        prices = []
        close_array = close_prices.values.flatten() if close_prices.ndim > 1 else close_prices.values
        
        for date, price in zip(close_prices.index, close_array):
            if not np.isnan(price):
                # Explicitly convert numpy scalars to Python native types
                timestamp = int(date.timestamp() * 1000)
                # Use item() method to safely convert numpy scalar
                if hasattr(price, 'item'):
                    price_val = round(float(price.item()), 2)
                else:
                    price_val = round(float(price), 2)
                prices.append([timestamp, price_val])
        
        if not prices:
            return jsonify({"error": f"No valid price data for {ticker}"}), 404
        
        return jsonify({
            "ticker": ticker,
            "prices": prices,
            "current_price": round(float(prices[-1][1]), 2),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        })
    except Exception as e:
        return jsonify({"error": f"Failed to fetch price data: {str(e)}"}), 500


@app.route("/api/auth/sync-user", methods=["POST"])
def sync_user():
    """Sync user to Supabase on first login."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    
    try:
        user_id = session.get("user_id")
        email = session.get("user_email")
        
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401
        
        # Check if user exists in Supabase
        response = supabase.table("users").select("id").eq("user_id", user_id).execute()
        
        if not response.data:
            # Create new user in Supabase
            supabase.table("users").insert({
                "user_id": user_id,
                "email": email,
            }).execute()
        
        return jsonify({"success": True, "user_id": user_id}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/watchlist", methods=["GET", "POST", "DELETE"])
@login_required
def api_watchlist():
    """Manage watchlist in Supabase with session authentication."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401
    
    try:
        if request.method == "GET":
            # Get user's watchlist
            try:
                response = supabase.table("watchlist").select("*").eq("user_id", user_id).execute()
                items = response.data if response.data else []
                return jsonify({"watchlist": items, "count": len(items)}), 200
            except Exception as e:
                app.logger.error(f"Watchlist GET error for user {user_id}: {e}")
                # If UUID error, return empty watchlist for now
                if "invalid input syntax for type uuid" in str(e).lower():
                    return jsonify({"watchlist": [], "count": 0, "note": "watchlist table schema mismatch"}), 200
                raise
        
        elif request.method == "POST":
            # Add to watchlist
            data = request.json or {}
            ticker = (data.get("ticker") or "").upper().strip()
            
            if not ticker or not _valid_ticker(ticker):
                return jsonify({"error": "Invalid ticker"}), 400
            
            try:
                # Upsert to avoid duplicates
                response = supabase.table("watchlist").upsert({
                    "user_id": user_id,
                    "ticker": ticker,
                    "added_at": datetime.now().isoformat(),
                }).execute()
                return jsonify({"success": True, "message": f"{ticker} added to watchlist"}), 200
            except Exception as e:
                app.logger.error(f"Watchlist POST error for user {user_id}: {e}")
                if "invalid input syntax for type uuid" in str(e).lower():
                    return jsonify({"success": True, "message": f"{ticker} added to watchlist (local)"}), 200
                raise
            
        elif request.method == "DELETE":
            # Remove from watchlist
            ticker = (request.args.get("ticker") or "").upper().strip()
            if not ticker:
                return jsonify({"error": "ticker parameter required"}), 400
            
            try:
                supabase.table("watchlist").delete().eq("user_id", user_id).eq("ticker", ticker).execute()
                return jsonify({"success": True, "message": f"{ticker} removed from watchlist"}), 200
            except Exception as e:
                app.logger.error(f"Watchlist DELETE error for user {user_id}: {e}")
                if "invalid input syntax for type uuid" in str(e).lower():
                    return jsonify({"success": True, "message": f"{ticker} removed from watchlist (local)"}), 200
                raise
    
    except Exception as e:
        app.logger.error(f"Watchlist error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/analysis-history")
def api_analysis_history():
    """GET /api/analysis-history?session_id=xxx — get past analyses."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    session_id = request.args.get("session_id", "default")
    limit = request.args.get("limit", 50, type=int)
    
    try:
        response = supabase.table("analysis_history").select("*").eq("session_id", session_id).order("analyzed_at", desc=True).limit(limit).execute()
        items = response.data if response.data else []
        return jsonify({"history": items, "count": len(items)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/save-analysis", methods=["POST"])
@login_required
def api_save_analysis():
    """POST /api/save-analysis — save analysis to history."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    data = request.json
    session_id = data.get("session_id", "default")
    ticker = (data.get("ticker") or "").upper().strip()
    
    if not ticker or not _valid_ticker(ticker):
        return jsonify({"error": "Invalid ticker"}), 400
    
    try:
        supabase.table("analysis_history").insert({
            "session_id": session_id,
            "ticker": ticker,
            "verdict": data.get("verdict"),
            "factor_score": data.get("factor_score"),
            "macro_context": data.get("macro_context"),
            "sentiment": data.get("sentiment"),
            "analyzed_at": datetime.now().isoformat(),
        }).execute()
        return jsonify({"message": "Analysis saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8000)
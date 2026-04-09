"""
Minimalist Flask app.py - main entry point
Routes and most logic have been moved to routes/ and services/
"""
import os
import sys
import queue
import subprocess
import threading
import time
import shutil
import re
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, send_from_directory, stream_with_context, session

# Load environment variables FIRST
load_dotenv()

# Import configuration
from config import Config, PROJECT_ROOT, FACTORLAB_ROOT, OUT_DIR, LOG_FILE, IMAGE_EXTENSIONS, SCRIPT, FACTORLAB_OUT

# Initialize supabase service
from services import init_supabase, get_supabase

# Import blueprints
from routes import auth_bp, login_required
from routes.dashboard import dashboard_bp, init_supabase as init_dashboard_supabase

# =====================================================================
# Flask App Setup
# =====================================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['SESSION_COOKIE_SECURE'] = Config.SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_HTTPONLY'] = Config.SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SAMESITE'] = Config.SESSION_COOKIE_SAMESITE
app.config['PERMANENT_SESSION_LIFETIME'] = Config.PERMANENT_SESSION_LIFETIME

# Initialize Supabase
supabase = init_supabase()
init_dashboard_supabase(supabase)

# Add factor-lab to Python path
if str(FACTORLAB_ROOT) not in sys.path:
    sys.path.insert(0, str(FACTORLAB_ROOT))

# =====================================================================
# Register Blueprints
# =====================================================================
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)

# =====================================================================
# Global Variables
# =====================================================================
_worker = {"proc": None, "thread": None, "running": False}
_cache = {}
_TICKER_RE = re.compile(r'^[A-Z]{1,5}$')
_CACHE_TTL_SECONDS = Config.CACHE_TTL_SECONDS


def _valid_ticker(ticker: str) -> bool:
    """Return True if ticker looks like a valid US equity symbol"""
    return bool(_TICKER_RE.match(ticker.upper())) if ticker else False


def _copy_images_to_flask():
    """Copy images from factor-lab/outputs to flask_app/outputs"""
    if FACTORLAB_OUT.exists():
        for file in FACTORLAB_OUT.iterdir():
            if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                dest = OUT_DIR / file.name
                shutil.copy2(file, dest)


def _run_script():
    """Run backtest script in background"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(FACTORLAB_ROOT)
    with LOG_FILE.open("w") as f:
        proc = subprocess.Popen(
            ["python3", str(SCRIPT)],
            stdout=f,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=str(FACTORLAB_ROOT),
        )
        _worker["proc"] = proc
        _worker["running"] = True
        proc.wait()
        _worker["running"] = False
        _worker["proc"] = None
        _copy_images_to_flask()


# =====================================================================
# Backtest Routes
# =====================================================================
@app.route("/run", methods=["POST"])
@login_required
def run_backtest():
    """Start backtest in background"""
    if _worker["running"]:
        return jsonify({"status": "already_running"}), 409
    t = threading.Thread(target=_run_script, daemon=True)
    _worker["thread"] = t
    t.start()
    time.sleep(0.1)
    return jsonify({"status": "started"})


@app.route("/status")
def status():
    """Get backtest status and log tail"""
    tail = ""
    if LOG_FILE.exists():
        with LOG_FILE.open("r") as f:
            lines = f.readlines()
            tail = "".join(lines[-200:])
    return jsonify({"running": _worker["running"], "log_tail": tail})


@app.route("/images")
def get_images():
    """Get list of output images"""
    images = []
    if OUT_DIR.exists():
        for file in OUT_DIR.iterdir():
            if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                images.append(file.name)
    return jsonify({"images": sorted(images)})


@app.route("/outputs/<path:filename>")
def outputs(filename):
    """Serve output files"""
    return send_from_directory(str(OUT_DIR), filename, as_attachment=True)


# =====================================================================
# Analysis Routes
# =====================================================================
@app.route("/api/analyze")
@login_required
def api_analyze():
    """GET /api/analyze?ticker=NVDA[&refresh=true]
    
    Analyzes a stock ticker using factor-lab modules.
    Results are cached for 15 minutes.
    """
    ticker = (request.args.get("ticker") or "").upper().strip()
    if not ticker:
        return jsonify({"error": "ticker parameter is required"}), 400
    if not _valid_ticker(ticker):
        return jsonify({"error": f"invalid ticker: {ticker}"}), 400

    refresh = request.args.get("refresh", "").lower() == "true"
    now = time.time()

    # Serve from cache if valid and not forced refresh
    if not refresh and ticker in _cache:
        entry = _cache[ticker]
        if entry["expires_at"] > now:
            cached_data = {**entry["data"], "_cache": {"hit": True, "expires_at": entry["expires_at"]}}
            app.logger.info(f"Cache hit for {ticker}")
            return jsonify(cached_data)

    # Cache miss — run analysis
    try:
        from src.scorer import analyze_ticker
        from src.factor_delay import add_factor_delay_context
        
        app.logger.info(f"Starting analysis for {ticker}")
        data = analyze_ticker(ticker)
        data = add_factor_delay_context(data)
        app.logger.info(f"Analysis complete for {ticker}")
    except Exception as e:
        app.logger.error(f"Analysis failed for {ticker}: {e}", exc_info=True)
        return jsonify({"error": "analysis failed; check server logs"}), 500

    if not data:
        app.logger.error(f"No data returned for {ticker}")
        return jsonify({"error": "no analysis data"}), 500
    
    expires_at = now + _CACHE_TTL_SECONDS
    _cache[ticker] = {"data": data, "expires_at": expires_at}
    response_data = {**data, "_cache": {"hit": False, "expires_at": expires_at}}
    return jsonify(response_data)


@app.route("/api/cache")
def api_cache():
    """GET /api/cache - List cached tickers and TTL"""
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
    
    Server-Sent Events endpoint. Streams backtest logs.
    """
    ticker = (request.args.get("ticker") or "").upper().strip()
    if not ticker:
        return jsonify({"error": "ticker parameter is required"}), 400
    if not _valid_ticker(ticker):
        return jsonify({"error": f"invalid ticker: {ticker}"}), 400

    def generate():
        q = queue.Queue(maxsize=1000)

        def _log_fn(msg: str) -> None:
            q.put(msg)

        def _run() -> None:
            try:
                from src.backtest import run_single_ticker_backtest
                run_single_ticker_backtest(ticker, log_fn=_log_fn)
            except Exception as exc:
                _log_fn(f"ERROR: {exc}")
            finally:
                q.put(None)

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


# =====================================================================
# Health & Status Routes
# =====================================================================
@app.route("/api/health")
def api_health():
    """GET /api/health - Health check"""
    now = time.time()
    cached_count = sum(1 for entry in _cache.values() if entry["expires_at"] > now)
    return jsonify({"status": "ok", "cached_tickers": cached_count})


@app.route("/api/latest-metrics")
def api_latest_metrics():
    """GET /api/latest-metrics"""
    return jsonify({"metrics": [], "message": "No backtest metrics available"})


@app.route("/api/all-backtests")
def api_all_backtests():
    """GET /api/all-backtests?limit=50"""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"backtests": [], "total": 0, "limit": limit})


# =====================================================================
# Price Chart & Historical Data Routes
# =====================================================================
@app.route("/api/price-chart")
@login_required
def api_price_chart():
    """GET /api/price-chart?ticker=AAPL&timeframe=6M
    
    Return price data for chart. Timeframe: 1M, 3M, 6M, 1Y, ALL
    """
    import yfinance as yf
    
    ticker = (request.args.get("ticker") or "").upper().strip()
    timeframe = (request.args.get("timeframe") or "6M").upper()
    
    if not ticker:
        return jsonify({"error": "ticker parameter is required"}), 400
    if not _valid_ticker(ticker):
        return jsonify({"error": f"invalid ticker: {ticker}"}), 400
    
    timeframe_map = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "ALL": 1000}
    lookback_days = timeframe_map.get(timeframe, 180)

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        data = yf.download(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True
        )
        
        if data.empty:
            return jsonify({"error": "no price data available"}), 404
        
        # Format for chart.js
        chart_data = {
            "dates": data.index.strftime("%Y-%m-%d").tolist(),
            "prices": data["Close"].round(2).tolist(),
            "volumes": data["Volume"].astype(int).tolist(),
        }
        return jsonify(chart_data)
    except Exception as e:
        app.logger.error(f"Price chart error for {ticker}: {e}")
        return jsonify({"error": str(e)}), 500


# =====================================================================
# Watchlist Routes (kept from original for API compatibility)
# =====================================================================
@app.route("/api/watchlist", methods=["GET", "POST", "DELETE"])
@login_required
def api_watchlist():
    """Manage user watchlist"""
    import yfinance as yf
    
    user_email = session.get("user_email")
    
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503

    try:
        if request.method == "GET":
            # Get watchlist
            response = supabase.table("watchlist").select("ticker").eq("email", user_email).execute()
            tickers = [item.get("ticker") for item in response.data] if response.data else []
            return jsonify({"watchlist": tickers}), 200

        elif request.method == "POST":
            # Add to watchlist
            ticker = request.json.get("ticker", "").upper().strip()
            if not _valid_ticker(ticker):
                return jsonify({"error": "invalid ticker"}), 400
            
            try:
                supabase.table("watchlist").insert({
                    "email": user_email,
                    "ticker": ticker,
                    "added_at": datetime.now().isoformat(),
                }).execute()
                return jsonify({"success": True, "message": f"{ticker} added"}), 200
            except Exception as e:
                error_str = str(e)
                if "duplicate" in error_str.lower() or "unique" in error_str.lower():
                    return jsonify({"success": True, "message": f"{ticker} already in watchlist"}), 200
                raise

        elif request.method == "DELETE":
            # Remove from watchlist
            ticker = request.json.get("ticker", "").upper().strip()
            if not _valid_ticker(ticker):
                return jsonify({"error": "invalid ticker"}), 400
            
            try:
                response = supabase.table("watchlist").select("tickers").eq("email", user_email).single().execute()
                
                if ticker in (response.data.get("tickers", []) if response.data else []):
                    supabase.table("watchlist").delete().eq("email", user_email).eq("ticker", ticker).execute()
                    return jsonify({"success": True, "message": f"{ticker} removed"}), 200
                else:
                    return jsonify({"success": True, "message": f"{ticker} not in watchlist"}), 200
            except Exception as e:
                error_str = str(e)
                if "No rows found" in error_str or "0 rows" in error_str:
                    return jsonify({"success": True, "message": "Watchlist not found"}), 200
                raise

    except Exception as e:
        app.logger.error(f"Watchlist error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/analysis-history")
def api_analysis_history():
    """GET /api/analysis-history?session_id=xxx"""
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


# =====================================================================
# Main Entry Point
# =====================================================================
if __name__ == "__main__":
    # Create output directories
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FACTORLAB_OUT.mkdir(parents=True, exist_ok=True)
    
    print("""
    ╔════════════════════════════════════════╗
    ║       AlphaLab Flask Server             ║
    ║  http://127.0.0.1:8000                 ║
    ╚════════════════════════════════════════╝
    """)
    
    app.run(debug=True, host="127.0.0.1", port=8000)

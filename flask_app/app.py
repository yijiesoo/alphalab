"""
Minimalist Flask app.py - main entry point
Routes and most logic have been moved to routes/ and services/
"""
import os
import sys
import uuid
import queue
import subprocess
import threading
import time
import shutil
import re
from pathlib import Path
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, send_from_directory, stream_with_context, session
import yfinance as yf
import pandas as pd

# Load environment variables FIRST
load_dotenv()

# Import yfinance utilities (caching, retry, metrics)
try:
    from flask_app.yfinance_utils import get_request_stats, yf_download_with_retry
    from flask_app.ticker_fetch import fetch_ticker_prices
except ImportError:
    from yfinance_utils import get_request_stats, yf_download_with_retry
    from ticker_fetch import fetch_ticker_prices

# Import configuration (handle both local and production imports)
try:
    from flask_app.config import Config, PROJECT_ROOT, FACTORLAB_ROOT, OUT_DIR, LOG_FILE, IMAGE_EXTENSIONS, SCRIPT, FACTORLAB_OUT
except ImportError:
    from config import Config, PROJECT_ROOT, FACTORLAB_ROOT, OUT_DIR, LOG_FILE, IMAGE_EXTENSIONS, SCRIPT, FACTORLAB_OUT

# Initialize supabase service
try:
    from flask_app.services import init_supabase, get_supabase
except ImportError:
    from services import init_supabase, get_supabase

# Import blueprints
try:
    from flask_app.routes import auth_bp, login_required
    from flask_app.routes.dashboard import dashboard_bp, init_supabase as init_dashboard_supabase
except ImportError:
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
# Separate sentiment cache keyed by ticker; longer TTL (4h) to reduce NewsAPI usage.
_sentiment_cache: dict = {}
_SENTIMENT_CACHE_TTL_SECONDS = 4 * 60 * 60  # 4 hours
_TICKER_RE = re.compile(r'^[A-Z]{1,5}([-\.][A-Z]{1,2})?$')
_CACHE_TTL_SECONDS = Config.CACHE_TTL_SECONDS


def _valid_ticker(ticker: str) -> bool:
    """Return True if ticker looks like a valid US equity symbol (e.g. AAPL, BRK-B, BF.B)"""
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
    return jsonify({
        "running": _worker["running"],
        "log_tail": tail,
        "_disclaimers": {
            "survivorship_bias": (
                "Backtest results use yfinance which only returns currently-listed tickers. "
                "Companies delisted between the start date and today (due to bankruptcy or "
                "acquisition) are excluded. This systematically overstates historical returns. "
                "Use point-in-time constituent data for production-grade research."
            ),
            "data_latency": (
                "All prices are end-of-day adjusted close. No intraday or real-time data is used."
            ),
        },
    })


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
            cached_data = {
                **entry["data"],
                "_cache": {"hit": True, "expires_at": entry["expires_at"]},
                "_disclaimers": {
                    "data_latency": (
                        "Price data is end-of-day (delayed). Do not use for intraday trading decisions."
                    ),
                    "survivorship_bias": (
                        "Analysis uses yfinance which only returns currently-listed tickers. "
                        "Delisted companies (bankruptcy, acquisitions) are excluded, causing an "
                        "optimistic bias in historical performance. Use a point-in-time data "
                        "provider for production-grade research."
                    ),
                },
            }
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
    response_data = {
        **data,
        "_cache": {"hit": False, "expires_at": expires_at},
        "_disclaimers": {
            "data_latency": (
                "Price data is end-of-day (delayed). Do not use for intraday trading decisions."
            ),
            "survivorship_bias": (
                "Analysis uses yfinance which only returns currently-listed tickers. "
                "Delisted companies (bankruptcy, acquisitions) are excluded, causing an "
                "optimistic bias in historical performance. Use a point-in-time data "
                "provider for production-grade research."
            ),
        },
    }
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


@app.route("/api/diagnostics")
def api_diagnostics():
    """GET /api/diagnostics - View request metrics and cache stats"""
    from flask_app.yfinance_utils import _ticker_cache, _cache_timestamps, CACHE_DURATION
    
    stats = get_request_stats()
    
    # Cache stats
    now = time.time()
    ticker_cache_size = len(_ticker_cache)
    ticker_cache_ttl = [(k, round(max(0, CACHE_DURATION - (now - _cache_timestamps.get(k, 0))))) 
                        for k in list(_ticker_cache.keys())[:10]]  # Show first 10
    
    return jsonify({
        "request_metrics": {
            "api_calls_this_hour": stats["api_calls"],
            "cache_hits_this_hour": stats["cache_hits"],
            "cache_misses_this_hour": stats["cache_misses"],
            "rate_limit_errors_this_hour": stats["rate_limits"],
            "cache_hit_ratio": round(stats["cache_hits"] / max(1, stats["cache_hits"] + stats["cache_misses"]), 2),
        },
        "ticker_cache": {
            "size": ticker_cache_size,
            "samples": dict(ticker_cache_ttl),
            "ttl_seconds": CACHE_DURATION,
        }
    })


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
        
        print(f"📈 Fetching price chart for {ticker} ({timeframe}, {lookback_days} days)")
        data = yf_download_with_retry(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
            logger=app.logger
        )
        
        if data.empty:
            return jsonify({"error": "no price data available"}), 404
        
        # Handle yfinance MultiIndex columns for single ticker
        # yfinance returns columns like ('Close', 'AAPL') for single ticker
        # or just 'Close' for multiple tickers
        if isinstance(data.columns, pd.MultiIndex):
            close_col = ('Close', ticker)
            volume_col = ('Volume', ticker)
        else:
            close_col = 'Close'
            volume_col = 'Volume'
        
        # Format for chart.js
        dates_list = data.index.strftime("%Y-%m-%d").tolist()
        prices_list = data[close_col].round(2).tolist()
        volumes_list = data[volume_col].astype(int).tolist()
        
        # Format as [date, price] pairs for chart
        chart_data = {
            "dates": dates_list,
            "prices": [[dates_list[i], prices_list[i]] for i in range(len(dates_list))],
            "volumes": volumes_list,
        }
        print(f"✅ Got {len(chart_data['dates'])} data points for {ticker}")
        return jsonify(chart_data)
    except Exception as e:
        import traceback
        print(f"❌ Price chart error for {ticker}: {e}")
        print(traceback.format_exc())
        app.logger.error(f"Price chart error for {ticker}: {e}", exc_info=True)
        return jsonify({"error": str(e), "debug": traceback.format_exc()}), 500


@app.route("/api/signal-history")
@login_required
def api_signal_history():
    """GET /api/signal-history?ticker=AAPL&timeframe=6M
    
    Return momentum signal history for a ticker over timeframe.
    """
    ticker = (request.args.get("ticker") or "").upper().strip()
    timeframe = (request.args.get("timeframe") or "6M").upper()
    
    if not ticker:
        return jsonify({"error": "ticker parameter is required"}), 400
    if not _valid_ticker(ticker):
        return jsonify({"error": f"invalid ticker: {ticker}"}), 400
    
    try:
        from src.signal_history import calculate_momentum_history
        
        print(f"📊 Fetching signal history for {ticker} ({timeframe})")
        result = calculate_momentum_history(ticker, timeframe)
        
        if "error" in result:
            print(f"⚠️ Signal history warning: {result['error']}")
            return jsonify(result), 200  # Return as 200 even if partial data
        
        print(f"✅ Got signal history: {len(result.get('history', []))} data points")
        return jsonify(result), 200
    except Exception as e:
        import traceback
        print(f"❌ Signal history error for {ticker}: {e}")
        print(traceback.format_exc())
        app.logger.error(f"Signal history error for {ticker}: {e}", exc_info=True)
        return jsonify({"error": str(e), "ticker": ticker, "timeframe": timeframe}), 200


@app.route("/api/portfolio/performance")
@login_required
def api_portfolio_performance():
    """GET /api/portfolio/performance?watchlist_id=xxx&period=3mo
    
    Calculate portfolio performance metrics for a watchlist.
    """
    watchlist_id = request.args.get("watchlist_id", "")
    period = request.args.get("period", "3mo")
    
    if not watchlist_id:
        return jsonify({"error": "watchlist_id parameter is required"}), 400
    
    try:
        user_email = session.get("user_email")
        
        # Get watchlist details
        if not supabase:
            return jsonify({"error": "Supabase not configured"}), 503
        
        print(f"📊 Fetching portfolio performance for watchlist: {watchlist_id}")
        response = supabase.table("watchlist").select("tickers").eq("id", watchlist_id).execute()
        
        if not response.data:
            return jsonify({"error": "Watchlist not found"}), 404
        
        tickers = response.data[0].get("tickers", [])
        if not tickers:
            return jsonify({
                "avg_return": 0,
                "best_performer": None,
                "worst_performer": None,
                "tickers_count": 0
            }), 200
        
        # Calculate returns for each ticker over period
        timeframe_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
        lookback_days = timeframe_map.get(period, 90)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        returns = []
        for ticker in tickers:
            try:
                data = yf.download(
                    ticker,
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                    progress=False
                )
                
                if len(data) > 0:
                    start_price = data['Close'].iloc[0]
                    end_price = data['Close'].iloc[-1]
                    ret = ((end_price - start_price) / start_price) * 100
                    returns.append({"ticker": ticker, "return": ret})
            except Exception:
                continue
        
        if not returns:
            return jsonify({
                "avg_return": 0,
                "best_performer": None,
                "worst_performer": None,
                "tickers_count": len(tickers)
            }), 200
        
        # Calculate metrics
        avg_return = sum(r["return"] for r in returns) / len(returns)
        best = max(returns, key=lambda x: x["return"])
        worst = min(returns, key=lambda x: x["return"])
        
        result = {
            "avg_return": round(avg_return, 2),
            "best_performer": {"ticker": best["ticker"], "return": round(best["return"], 2)},
            "worst_performer": {"ticker": worst["ticker"], "return": round(worst["return"], 2)},
            "tickers_count": len(tickers),
            "period": period,
            "all_returns": returns
        }
        
        print(f"✅ Portfolio performance: {result['avg_return']}% avg return")
        return jsonify(result), 200
    except Exception as e:
        import traceback
        print(f"❌ Portfolio performance error: {e}")
        print(traceback.format_exc())
        app.logger.error(f"Portfolio performance error: {e}", exc_info=True)
        return jsonify({"error": str(e), "avg_return": 0}), 200


# =====================================================================
# Watchlist Routes (kept from original for API compatibility)
# =====================================================================
@app.route("/api/watchlist", methods=["GET", "POST", "DELETE"])
@login_required
def api_watchlist():
    """Manage user watchlist"""
    user_email = session.get("user_email")
    
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503

    try:
        if request.method == "GET":
            # Get watchlist (tickers stored as array in single row per user)
            print(f"🔍 GET watchlist for user: {user_email}")
            response = supabase.table("watchlist").select("tickers").eq("email", user_email).execute()
            print(f"✅ Response data: {response.data}")
            tickers = []
            if response.data and len(response.data) > 0:
                tickers = response.data[0].get("tickers", [])
            return jsonify({"watchlist": tickers}), 200

        elif request.method == "POST":
            # Add to watchlist
            ticker = request.json.get("ticker", "").upper().strip()
            if not _valid_ticker(ticker):
                return jsonify({"error": "invalid ticker"}), 400
            
            try:
                print(f"✏️ Adding {ticker} to watchlist for {user_email}")
                # Get existing watchlist
                response = supabase.table("watchlist").select("tickers").eq("email", user_email).execute()
                tickers = []
                watchlist_id = None
                
                if response.data and len(response.data) > 0:
                    # User already has a watchlist, update it
                    watchlist_id = response.data[0].get("id")
                    tickers = response.data[0].get("tickers", [])
                    if ticker not in tickers:
                        tickers.append(ticker)
                        supabase.table("watchlist").update({"tickers": tickers}).eq("id", watchlist_id).execute()
                    else:
                        return jsonify({"success": True, "message": f"{ticker} already in watchlist"}), 200
                else:
                    # Create new watchlist for user
                    tickers = [ticker]
                    supabase.table("watchlist").insert({
                        "email": user_email,
                        "tickers": tickers,
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
                print(f"🗑️ Deleting {ticker} from watchlist for {user_email}")
                # Get existing watchlist
                response = supabase.table("watchlist").select("tickers, id").eq("email", user_email).execute()
                
                if response.data and len(response.data) > 0:
                    watchlist_id = response.data[0].get("id")
                    tickers = response.data[0].get("tickers", [])
                    
                    if ticker in tickers:
                        tickers.remove(ticker)
                        supabase.table("watchlist").update({"tickers": tickers}).eq("id", watchlist_id).execute()
                        return jsonify({"success": True, "message": f"{ticker} removed"}), 200
                    else:
                        return jsonify({"success": True, "message": "Ticker not in watchlist"}), 200
                else:
                    return jsonify({"success": True, "message": "Watchlist not found"}), 200
            except Exception as e:
                error_str = str(e)
                if "No rows found" in error_str or "0 rows" in error_str:
                    return jsonify({"success": True, "message": "Watchlist not found"}), 200
                app.logger.error(f"Error deleting watchlist item: {e}", exc_info=True)
                raise

    except Exception as e:
        import traceback
        print(f"❌ Watchlist error: {e}")
        print(traceback.format_exc())
        app.logger.error(f"Watchlist error: {e}", exc_info=True)
        return jsonify({"error": str(e), "debug": traceback.format_exc()}), 500


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
# Save Analysis Route
# =====================================================================
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


# =====================================================================
# Beginner Guide Route
# =====================================================================
@app.route("/api/beginner-guide/<ticker>", methods=["GET"])
def beginner_guide(ticker):
    """GET /api/beginner-guide/<ticker>"""
    ticker = (ticker or "").upper().strip()
    if not _valid_ticker(ticker):
        return jsonify({"error": f"invalid ticker: {ticker}"}), 400
    
    try:
        from src.beginner_guide import explain_signal
        from src.scorer import analyze_ticker
        
        # Get the analysis first
        analysis = analyze_ticker(ticker)
        
        # Get beginner-friendly explanation
        explanation = explain_signal(analysis)
        
        return jsonify({"explanation": explanation, "ticker": ticker, "analysis": analysis})
    except Exception as e:
        app.logger.error(f"Beginner guide error for {ticker}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# =====================================================================
# Watchlists Management Routes
# =====================================================================
@app.route("/api/watchlists", methods=["GET"])
@login_required
def get_watchlists():
    """GET /api/watchlists — get all watchlists for user"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    
    user_email = session.get("user_email")
    
    if not user_email:
        print(f"⚠️ No user_email in session")
        return jsonify({"error": "No user session", "watchlists": []}), 200
    
    try:
        print(f"🔍 GET watchlists for user: {user_email}")
        response = supabase.table("watchlists").select("*").eq("email", user_email).execute()
        watchlists = response.data if response.data else []
        print(f"✅ Found {len(watchlists)} watchlists")
        return jsonify({"watchlists": watchlists}), 200
    except Exception as e:
        import traceback
        print(f"❌ Error getting watchlists: {e}")
        print(traceback.format_exc())
        app.logger.error(f"Error getting watchlists: {e}", exc_info=True)
        # Return 200 with empty list instead of 500 to prevent UI breakage
        return jsonify({"error": str(e), "watchlists": [], "debug": str(e)}), 200


@app.route("/api/watchlists", methods=["POST"])
@login_required
def create_watchlist():
    """POST /api/watchlists — create new watchlist"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    
    user_email = session.get("user_email")
    data = request.json
    name = data.get("name", "").strip()
    
    if not name:
        return jsonify({"error": "Watchlist name is required"}), 400
    
    try:
        watchlist_id = str(uuid.uuid4())
        print(f"✏️ Creating watchlist '{name}' for user: {user_email}")
        supabase.table("watchlists").insert({
            "id": watchlist_id,
            "email": user_email,
            "name": name,
            "tickers": [],
            "created_at": datetime.now().isoformat(),
        }).execute()
        print(f"✅ Created watchlist: {watchlist_id}")
        return jsonify({"success": True, "watchlist_id": watchlist_id}), 201
    except Exception as e:
        import traceback
        print(f"❌ Error creating watchlist: {e}")
        print(traceback.format_exc())
        app.logger.error(f"Error creating watchlist: {e}", exc_info=True)
        return jsonify({"error": str(e), "debug": traceback.format_exc()}), 500


@app.route("/api/watchlists/<watchlist_id>", methods=["DELETE"])
@login_required
def delete_watchlist(watchlist_id):
    """DELETE /api/watchlists/<watchlist_id>"""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    
    try:
        print(f"🗑️ Deleting watchlist: {watchlist_id}")
        supabase.table("watchlists").delete().eq("id", watchlist_id).execute()
        print(f"✅ Deleted watchlist: {watchlist_id}")
        return jsonify({"success": True}), 200
    except Exception as e:
        import traceback
        print(f"❌ Error deleting watchlist: {e}")
        print(traceback.format_exc())
        app.logger.error(f"Error deleting watchlist: {e}", exc_info=True)
        return jsonify({"error": str(e), "debug": traceback.format_exc()}), 500


# =====================================================================
# Portfolio Holdings API
# =====================================================================
@app.route("/api/portfolio/holdings", methods=["GET", "POST", "PUT", "DELETE"])
@login_required
def api_portfolio_holdings():
    """Manage portfolio holdings with entry prices and quantities"""
    user_email = session.get("user_email")
    
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503

    try:
        if request.method == "GET":
            # Get all holdings for user
            print(f"🔍 GET portfolio holdings for user: {user_email}")
            response = supabase.table("portfolio_holdings").select("*").eq("email", user_email).execute()
            holdings = response.data or []
            print(f"✅ Found {len(holdings)} holdings")
            return jsonify({"holdings": holdings}), 200

        elif request.method == "POST":
            # Add new holding
            data = request.json
            ticker = data.get("ticker", "").upper().strip()
            quantity = float(data.get("quantity", 0))
            entry_price = float(data.get("entry_price", 0))
            
            if not _valid_ticker(ticker):
                return jsonify({"error": "invalid ticker"}), 400
            if quantity <= 0 or entry_price <= 0:
                return jsonify({"error": "quantity and entry_price must be positive"}), 400
            
            print(f"✏️ Adding/Updating holding: {ticker} x{quantity} @ ${entry_price} for {user_email}")
            
            try:
                # Try to insert first
                result = supabase.table("portfolio_holdings").insert({
                    "email": user_email,
                    "ticker": ticker,
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "entry_date": data.get("entry_date", datetime.now().isoformat()),
                }).execute()
                print(f"✅ New holding created: {ticker}")
                return jsonify({"success": True, "message": f"{ticker} holding added"}), 201
            except Exception as e:
                error_str = str(e)
                # If duplicate key error, update instead
                if "23505" in error_str or "duplicate key" in error_str.lower():
                    print(f"🔄 Holding exists, updating: {ticker}")
                    try:
                        # Get the existing record
                        existing = supabase.table("portfolio_holdings").select("id").eq("email", user_email).eq("ticker", ticker).execute()
                        if existing.data and len(existing.data) > 0:
                            holding_id = existing.data[0]["id"]
                            supabase.table("portfolio_holdings").update({
                                "quantity": quantity,
                                "entry_price": entry_price,
                                "entry_date": data.get("entry_date", datetime.now().isoformat()),
                                "updated_at": datetime.now().isoformat(),
                            }).eq("id", holding_id).execute()
                            print(f"✅ Holding updated: {ticker}")
                            return jsonify({"success": True, "message": f"{ticker} holding updated"}), 200
                    except Exception as update_e:
                        print(f"❌ Update error: {update_e}")
                        return jsonify({"error": f"Error updating holding: {str(update_e)}"}), 500
                else:
                    print(f"❌ Insert error: {e}")
                    return jsonify({"error": str(e)}), 500

        elif request.method == "PUT":
            # Update holding
            data = request.json
            holding_id = data.get("id")
            quantity = float(data.get("quantity", 0))
            entry_price = float(data.get("entry_price", 0))
            
            if quantity <= 0 or entry_price <= 0:
                return jsonify({"error": "quantity and entry_price must be positive"}), 400
            
            print(f"✏️ Updating holding: {holding_id}")
            supabase.table("portfolio_holdings").update({
                "quantity": quantity,
                "entry_price": entry_price,
            }).eq("id", holding_id).execute()
            return jsonify({"success": True}), 200

        elif request.method == "DELETE":
            # Delete holding
            ticker = request.json.get("ticker", "").upper().strip()
            
            print(f"🗑️ Deleting holding: {ticker}")
            supabase.table("portfolio_holdings").delete().eq("email", user_email).eq("ticker", ticker).execute()
            return jsonify({"success": True}), 200

    except Exception as e:
        import traceback
        print(f"❌ Error managing holdings: {e}")
        print(traceback.format_exc())
        app.logger.error(f"Error managing holdings: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/portfolio/summary", methods=["GET"])
@login_required
def api_portfolio_summary():
    """Get portfolio summary with accurate P&L calculations"""
    user_email = session.get("user_email")
    
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503

    try:
        # Get all holdings
        response = supabase.table("portfolio_holdings").select("*").eq("email", user_email).execute()
        holdings = response.data or []
        
        if not holdings:
            return jsonify({
                "total_invested": 0,
                "total_current_value": 0,
                "total_gain_loss": 0,
                "total_gain_loss_pct": 0,
                "holdings_count": 0,
                "holdings": [],
                "data_timestamp": datetime.now().isoformat()
            }), 200
        
        # Calculate current values and P&L
        total_invested = 0
        total_current_value = 0
        holding_details = []
        
        for holding in holdings:
            ticker = holding["ticker"]
            quantity = float(holding["quantity"])
            entry_price = float(holding["entry_price"])
            
            # Get current price using batch fetching (avoids expensive quoteSummary endpoint)
            current_price = entry_price
            try:
                # Use our optimized batch fetcher instead of yf.Ticker().info
                prices = fetch_ticker_prices([ticker], period="5d", logger=None)
                if prices and ticker in prices:
                    fetched_price = prices[ticker].get("current_price", 0)
                    if fetched_price > 0:
                        current_price = float(fetched_price)
                    else:
                        # Fallback: get from history
                        hist = yf.download(ticker, period="5d", progress=False,
                                           auto_adjust=True, show_errors=False)
                        if not hist.empty:
                            current_price = float(hist['Close'].iloc[-1])
                else:
                    # If batch fetch fails, try history
                    hist = yf.download(ticker, period="5d", progress=False,
                                       auto_adjust=True, show_errors=False)
                    if not hist.empty:
                        current_price = float(hist['Close'].iloc[-1])
                current_price = float(current_price) if current_price else entry_price
            except Exception as price_error:
                print(f"⚠️ Price fetch error for {ticker}: {price_error}")
                current_price = entry_price
            
            invested = quantity * entry_price
            current_value = quantity * current_price
            gain_loss = current_value - invested
            gain_loss_pct = (gain_loss / invested * 100) if invested > 0 else 0
            
            total_invested += invested
            total_current_value += current_value
            
            # Determine position status for beginner-friendly display
            position_status = "holding"
            if gain_loss_pct > 15:
                position_status = "winning"
            elif gain_loss_pct < -10:
                position_status = "losing"
            
            holding_details.append({
                "ticker": ticker,
                "quantity": quantity,
                "entry_price": round(entry_price, 2),
                "current_price": round(current_price, 2),
                "invested": round(invested, 2),
                "current_value": round(current_value, 2),
                "gain_loss": round(gain_loss, 2),
                "gain_loss_pct": round(gain_loss_pct, 2),
                "position_status": position_status,  # "winning", "losing", or "holding"
            })
        
        total_gain_loss = total_current_value - total_invested
        total_gain_loss_pct = (total_gain_loss / total_invested * 100) if total_invested > 0 else 0
        
        # Sort by gain/loss (best performers first)
        holding_details.sort(key=lambda x: x["gain_loss"], reverse=True)
        
        print(f"📊 Portfolio Summary - Invested: ${total_invested:.2f}, Current: ${total_current_value:.2f}, P&L: ${total_gain_loss:.2f}")
        
        return jsonify({
            "total_invested": round(total_invested, 2),
            "total_current_value": round(total_current_value, 2),
            "total_gain_loss": round(total_gain_loss, 2),
            "total_gain_loss_pct": round(total_gain_loss_pct, 2),
            "holdings_count": len(holdings),
            "holdings": holding_details,
            "data_timestamp": datetime.now().isoformat(),
        }), 200
    
    except Exception as e:
        import traceback
        print(f"❌ Error calculating portfolio summary: {e}")
        print(traceback.format_exc())
        app.logger.error(f"Error calculating portfolio summary: {e}", exc_info=True)
        return jsonify({"error": str(e), "holdings": []}), 500


# =====================================================================
# FEEDBACK ENDPOINT
# =====================================================================
@app.route("/api/feedback", methods=["POST"])
@login_required
def submit_feedback():
    """
    Send user feedback to admin email
    """
    try:
        data = request.get_json()
        feedback_text = data.get("feedback", "").strip()
        page = data.get("page", "unknown")
        timestamp = data.get("timestamp", datetime.now().isoformat())
        
        if not feedback_text:
            return jsonify({"error": "Feedback text is required"}), 400
        
        # Get user email from session
        user_email = session.get("user_email", "anonymous")
        
        # Send email to admin
        send_feedback_email(user_email, feedback_text, page, timestamp)
        
        print(f"✅ Feedback email sent from {user_email}: {feedback_text[:50]}...")
        return jsonify({"message": "Feedback received successfully"}), 200
    
    except Exception as e:
        import traceback
        print(f"❌ Error sending feedback: {e}")
        print(traceback.format_exc())
        app.logger.error(f"Error sending feedback: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def send_feedback_email(user_email, feedback_text, page, timestamp):
    """
    Send feedback email to admin
    """
    try:
        # Email configuration
        sender_email = os.getenv("GMAIL_USER", "alphalab.feedback@gmail.com")
        sender_password = os.getenv("GMAIL_PASSWORD", "")
        recipient_email = "sooyijie111@gmail.com"
        
        # Create message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = f"📬 AlphaLab Feedback from {user_email}"
        
        # Email body
        body = f"""
        <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1F2937;">
                <h2 style="color: #3B82F6;">📬 New Feedback Received</h2>
                
                <div style="background: #F8FAFC; padding: 16px; border-radius: 8px; margin: 16px 0;">
                    <p><strong>From:</strong> {user_email}</p>
                    <p><strong>Page:</strong> {page}</p>
                    <p><strong>Time:</strong> {timestamp}</p>
                </div>
                
                <div style="background: #FFFFFF; padding: 16px; border: 1px solid #E2E8F0; border-radius: 8px; margin: 16px 0;">
                    <h3 style="color: #1F2937; margin-top: 0;">Feedback:</h3>
                    <p style="white-space: pre-wrap; color: #4B5563; line-height: 1.6;">{feedback_text}</p>
                </div>
                
                <p style="color: #6B7280; font-size: 0.9em; margin-top: 24px;">
                    — AlphaLab Feedback System
                </p>
            </body>
        </html>
        """
        
        message.attach(MIMEText(body, "html"))
        
        # Send email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(message)
        
        print(f"✅ Email sent to {recipient_email}")
    
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        import traceback
        traceback.print_exc()


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

import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, send_from_directory, stream_with_context
import yfinance as yf

# Supabase
try:
    from supabase import create_client, Client
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
except ImportError:
    supabase = None

# Load environment variables from a .env file if one is present
load_dotenv()

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
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
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
            return jsonify({
                **entry["data"],
                "_cache": {"hit": True, "expires_at": entry["expires_at"]},
            })

    # Cache miss (or refresh requested) — run analysis
    try:
        from src.scorer import analyze_ticker
        data = analyze_ticker(ticker)
    except Exception as e:
        app.logger.error(f"Analysis failed for {ticker}: {e}")
        return jsonify({"error": "analysis failed; check server logs"}), 500

    expires_at = now + _CACHE_TTL_SECONDS
    _cache[ticker] = {"data": data, "expires_at": expires_at}
    return jsonify({**data, "_cache": {"hit": False, "expires_at": expires_at}})


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
        prices = [
            [int(date.timestamp() * 1000), round(float(price), 2)]
            for date, price in zip(close_prices.index, close_prices.values)
            if not __import__('pandas').isna(price)
        ]
        
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


@app.route("/api/watchlist", methods=["GET", "POST", "DELETE"])
def api_watchlist():
    """Manage watchlist in Supabase."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    session_id = request.args.get("session_id", "default")
    
    if request.method == "GET":
        # Get watchlist
        try:
            response = supabase.table("watchlist").select("*").eq("session_id", session_id).execute()
            items = response.data if response.data else []
            return jsonify({"watchlist": items, "count": len(items)})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    elif request.method == "POST":
        # Add to watchlist
        data = request.json
        ticker = (data.get("ticker") or "").upper().strip()
        
        if not ticker or not _valid_ticker(ticker):
            return jsonify({"error": "Invalid ticker"}), 400
        
        try:
            # Check if already exists
            existing = supabase.table("watchlist").select("*").eq("session_id", session_id).eq("ticker", ticker).execute()
            if existing.data:
                return jsonify({"error": "Already in watchlist"}), 409
            
            # Add new entry
            response = supabase.table("watchlist").insert({
                "session_id": session_id,
                "ticker": ticker,
                "added_at": datetime.now().isoformat(),
            }).execute()
            return jsonify({"message": "Added to watchlist", "data": response.data[0] if response.data else {}})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    elif request.method == "DELETE":
        # Remove from watchlist
        ticker = (request.args.get("ticker") or "").upper().strip()
        if not ticker:
            return jsonify({"error": "ticker parameter required"}), 400
        
        try:
            supabase.table("watchlist").delete().eq("session_id", session_id).eq("ticker", ticker).execute()
            return jsonify({"message": "Removed from watchlist"})
        except Exception as e:
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
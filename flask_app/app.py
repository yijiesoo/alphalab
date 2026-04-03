import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, send_from_directory, stream_with_context

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


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8000)
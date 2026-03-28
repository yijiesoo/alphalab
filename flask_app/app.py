from flask import Flask, render_template, jsonify, send_from_directory, request
import os
import subprocess
import threading
from pathlib import Path
import json 
from supabase import create_client, Client
import time
import shutil
from dotenv import load_dotenv
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

# Configure these to match your repo layout
PROJECT_ROOT = Path("/Users/yjsoo/Documents/alphalab")
FACTORLAB_ROOT = PROJECT_ROOT / "factor-lab"
FACTORLAB_SRC = FACTORLAB_ROOT / "src"
SCRIPT = FACTORLAB_ROOT / "scripts" / "run_backtest.py"
FACTORLAB_OUT = FACTORLAB_ROOT / "outputs"

APP_ROOT = Path(__file__).resolve().parent
OUT_DIR = APP_ROOT / "outputs"
LOG_FILE = OUT_DIR / "backtest.log"

OUT_DIR.mkdir(parents=True, exist_ok=True)
FACTORLAB_OUT.mkdir(parents=True, exist_ok=True)

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = None

try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Supabase connected successfully")
    else:
        logger.warning("⚠️  Supabase credentials not found in .env")
except Exception as e:
    logger.warning(f"⚠️  Supabase connection failed: {e}. Running without Supabase integration.")

app = Flask(__name__)
_worker = {
    "proc": None,
    "thread": None,
    "running": False,
    "start_time": None,
    "exit_code": None,
    "error_message": None,
}

# Image extensions to look for
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'}


def _copy_images_to_flask():
    """Copy images from factor-lab/outputs to flask_app/outputs"""
    try:
        if FACTORLAB_OUT.exists():
            for file in FACTORLAB_OUT.iterdir():
                if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                    dest = OUT_DIR / file.name
                    shutil.copy2(file, dest)
                    logger.info(f"Copied image: {file.name}")
    except Exception as e:
        logger.error(f"Error copying images: {e}")


def _format_metrics_for_display(metrics: dict) -> dict:
    """Format metrics dict for cleaner display in UI"""
    if not metrics:
        return {}
    
    formatted = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            # Format floats with appropriate precision
            if key.endswith('_rate') or 'pvalue' in key.lower():
                formatted[key] = round(value, 4)
            else:
                formatted[key] = round(value, 2)
        else:
            formatted[key] = value
    
    return formatted


def _get_backtest_summary() -> dict:
    """Get summary of the most recent backtest from Supabase"""
    if not supabase:
        return {}
    
    try:
        response = supabase.table("backtest_runs").select("*").order(
            "created_at", desc=True
        ).limit(1).execute()
        
        if response.data:
            run = response.data[0]
            return {
                "backtest_id": run.get("id"),
                "created_at": run.get("created_at"),
                "metrics": _format_metrics_for_display(run.get("metrics", {})),
                "stress_test": run.get("stress_test", {}),
            }
    except Exception as e:
        logger.error(f"Error getting backtest summary: {e}")
    
    return {}

@app.route("/backtest-history")
def backtest_history():
    """Get list of recent backtest runs."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        limit = request.args.get("limit", default=20, type=int)
        response = supabase.table("backtest_runs").select("*").order(
            "created_at", desc=True
        ).limit(limit).execute()
        
        # Format metrics for each backtest
        backtests = []
        for run in response.data:
            run["metrics"] = _format_metrics_for_display(run.get("metrics", {}))
            backtests.append(run)
        
        return jsonify({"backtests": backtests, "count": len(backtests)})
    except Exception as e:
        logger.error(f"Error fetching backtest history: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/backtest/<backtest_id>/details")
def backtest_details(backtest_id):
    """Get details of a specific backtest."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 500
    
    try:
        # Get backtest record
        response = supabase.table("backtest_runs").select("*").eq(
            "id", backtest_id
        ).execute()
        
        if not response.data:
            return jsonify({"error": "Backtest not found"}), 404
        
        backtest = response.data[0]
        metrics = backtest.get("metrics", {})
        
        # Parse metrics if it's a string
        if isinstance(metrics, str):
            metrics = json.loads(metrics)
        
        backtest["metrics"] = _format_metrics_for_display(metrics)
        
        # Get associated images
        images_response = supabase.table("backtest_images").select("*").eq(
            "backtest_id", backtest_id
        ).execute()
        
        return jsonify({
            "backtest": backtest,
            "images": images_response.data,
        })
    except Exception as e:
        logger.error(f"Error fetching backtest details: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/compare-backtests")
def compare_backtests():
    """Compare multiple backtest runs."""
    ids = request.args.getlist("ids[]")
    
    if not supabase or not ids:
        return jsonify({"error": "Missing parameters"}), 400
    
    try:
        runs = []
        for bid in ids:
            response = supabase.table("backtest_runs").select("*").eq(
                "id", bid
            ).execute()
            if response.data:
                runs.append(response.data[0])
        
        # Extract comparable metrics
        comparison = []
        for run in runs:
            m = run.get("metrics", {})
            comparison.append({
                "id": run["id"],
                "created_at": run["created_at"],
                "cagr": m.get("cagr"),
                "sharpe_ratio": m.get("sharpe_ratio"),
                "sortino_ratio": m.get("sortino_ratio"),
                "calmar_ratio": m.get("calmar_ratio"),
                "max_drawdown": m.get("max_drawdown"),
                "win_rate": m.get("win_rate"),
                "ic": m.get("ic"),
                "ic_pvalue": m.get("ic_pvalue"),
            })
        
        return jsonify({"comparison": comparison, "count": len(comparison)})
    except Exception as e:
        logger.error(f"Error comparing backtests: {e}")
        return jsonify({"error": str(e)}), 500


def _run_script():
    """Run backtest script with comprehensive error handling and logging."""
    _worker["start_time"] = datetime.now()
    _worker["error_message"] = None
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(FACTORLAB_ROOT)
    
    try:
        with LOG_FILE.open("w") as f:
            logger.info("Starting backtest subprocess...")
            proc = subprocess.Popen(
                ["python3", str(SCRIPT)],
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=str(FACTORLAB_ROOT),
            )
            _worker["proc"] = proc
            _worker["running"] = True
            
            # Wait for process to complete
            exit_code = proc.wait()
            _worker["exit_code"] = exit_code
            _worker["running"] = False
            _worker["proc"] = None
            
            if exit_code == 0:
                logger.info("✅ Backtest completed successfully")
                # Copy images
                _copy_images_to_flask()
            else:
                error_msg = f"Backtest failed with exit code {exit_code}"
                logger.error(error_msg)
                _worker["error_message"] = error_msg
                
    except Exception as e:
        logger.error(f"Error running backtest: {e}")
        _worker["error_message"] = str(e)
        _worker["running"] = False
        _worker["proc"] = None
    
    logger.info("Backtest runner finished")

@app.route("/")
def index():
    """Serve the main page"""
    return render_template("index.html")


@app.route("/api/summary")
def api_summary():
    """Get summary of the latest backtest"""
    summary = _get_backtest_summary()
    return jsonify(summary)


@app.route("/api/latest-metrics")
def api_latest_metrics():
    """Get latest backtest metrics from Supabase"""
    if not supabase:
        return jsonify({"metrics": None, "message": "Supabase not configured"}), 200
    
    try:
        response = supabase.table("backtest_runs").select("*").order(
            "created_at", desc=True
        ).limit(1).execute()
        
        if not response.data:
            return jsonify({"metrics": None}), 200
        
        backtest = response.data[0]
        metrics = backtest.get("metrics", {})
        
        # Parse metrics if it's a string (from Supabase JSON column)
        if isinstance(metrics, str):
            metrics = json.loads(metrics)
        
        # Format the metrics for display
        formatted_metrics = _format_metrics_for_display(metrics)
        
        return jsonify({
            "metrics": formatted_metrics,
            "backtest_id": backtest["id"],
            "created_at": backtest["created_at"],
        })
    
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return jsonify({"metrics": None, "error": str(e)}), 200

@app.route("/api/all-backtests")
def api_all_backtests():
    """Get all backtest runs from Supabase"""
    if not supabase:
        return jsonify({"backtests": [], "count": 0, "message": "Supabase not configured"}), 200
    
    try:
        limit = request.args.get("limit", default=50, type=int)
        response = supabase.table("backtest_runs").select("*").order(
            "created_at", desc=True
        ).limit(limit).execute()
        
        backtests = []
        for run in response.data:
            metrics = run.get("metrics", {})
            
            # Parse metrics if it's a string (from Supabase JSON column)
            if isinstance(metrics, str):
                metrics = json.loads(metrics)
            
            backtests.append({
                "id": run.get("id"),
                "created_at": run.get("created_at"),
                "metrics": _format_metrics_for_display(metrics),
                "num_stocks": run.get("num_stocks"),
                "num_rebalances": run.get("num_rebalances"),
            })
        
        return jsonify({
            "backtests": backtests,
            "count": len(backtests),
        })
    
    except Exception as e:
        logger.error(f"Error fetching backtests: {e}")
        return jsonify({"backtests": [], "count": 0, "error": str(e)}), 200

@app.route("/run", methods=["POST"])
def run_backtest():
    """Start a new backtest run"""
    if _worker["running"]:
        return jsonify({
            "status": "already_running",
            "start_time": _worker["start_time"].isoformat() if _worker["start_time"] else None
        }), 409
    
    try:
        t = threading.Thread(target=_run_script, daemon=True)
        _worker["thread"] = t
        t.start()
        time.sleep(0.1)
        logger.info("Backtest started")
        return jsonify({"status": "started", "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.error(f"Error starting backtest: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/status")
def status():
    """Get current backtest status and log tail"""
    tail = ""
    if LOG_FILE.exists():
        try:
            with LOG_FILE.open("r") as f:
                lines = f.readlines()
                tail = "".join(lines[-300:])  # Increased from 200 to 300 lines
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
    
    return jsonify({
        "running": _worker["running"],
        "log_tail": tail,
        "start_time": _worker["start_time"].isoformat() if _worker["start_time"] else None,
        "exit_code": _worker["exit_code"],
        "error_message": _worker["error_message"],
    })


@app.route("/images")
def get_images():
    """Return list of images in the output folder"""
    images = []
    try:
        if OUT_DIR.exists():
            for file in OUT_DIR.iterdir():
                if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS:
                    images.append({
                        "name": file.name,
                        "size": file.stat().st_size,
                        "modified": datetime.fromtimestamp(file.stat().st_mtime).isoformat(),
                    })
    except Exception as e:
        logger.error(f"Error getting images: {e}")
    
    return jsonify({"images": sorted(images, key=lambda x: x["name"])})


@app.route("/outputs/<path:filename>")
def outputs(filename):
    """Serve files from outputs directory"""
    try:
        return send_from_directory(str(OUT_DIR), filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Error serving file {filename}: {e}")
        return jsonify({"error": "File not found"}), 404


@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "supabase_configured": supabase is not None,
    })


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    logger.error(f"Server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Starting Factor Lab Flask App")
    logger.info("="*60)
    logger.info("Open browser to: http://127.0.0.1:8000")
    logger.info("="*60)
    
    app.run(
        debug=True,
        host="0.0.0.0",
        port=8000,  # Changed from 5000
        use_reloader=False,
    )
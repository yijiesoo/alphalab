from flask import Flask, render_template, jsonify, send_from_directory, request
import os
import subprocess
import threading
from pathlib import Path
import time
import shutil

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

app = Flask(__name__)
_worker = {"proc": None, "thread": None, "running": False}

# Image extensions to look for
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'}


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


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
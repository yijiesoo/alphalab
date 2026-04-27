"""
Dashboard routes: Home, Analyze, and dashboard API endpoints
"""
from flask import Blueprint, render_template, session, jsonify, request
from datetime import datetime
import pandas as pd
import yfinance as yf
from . import login_required
from ..config import Config

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__)

# Initialize cache and supabase globally
_cache = {}
supabase = None

VALID_RISKS = {"conservative", "moderate", "aggressive"}
VALID_HORIZONS = {"short", "medium", "long"}


def init_supabase(sb):
    """Initialize supabase instance"""
    global supabase
    supabase = sb


def _normalize_close(data: pd.DataFrame, tickers: list) -> pd.DataFrame:
    """Return a DataFrame with one column per ticker from yf.download output.

    yfinance (1.x+) returns MultiIndex columns for all downloads.
    Older versions return flat columns with a Series for single-ticker downloads.
    This helper normalises both so callers always get a plain DataFrame.
    """
    if isinstance(data.columns, pd.MultiIndex):
        close_df = data["Close"]
        if isinstance(close_df, pd.Series):
            close_df = close_df.to_frame(name=tickers[0])
    else:
        close_data = data["Close"]
        if isinstance(close_data, pd.Series):
            close_df = close_data.to_frame(name=tickers[0])
        else:
            close_df = close_data
    return close_df


# =====================================================================
# View Routes (HTML Pages)
# =====================================================================
@dashboard_bp.route("/")
@login_required
def index():
    """Root redirects to home/dashboard"""
    from flask import redirect, url_for
    return redirect(url_for("dashboard.home"))


@dashboard_bp.route("/home")
@login_required
def home():
    """Home/Dashboard page - shows portfolio overview"""
    if not session.get("onboarding_complete"):
        from flask import redirect, url_for
        return redirect(url_for("dashboard.onboarding"))
    return render_template("home.html")

# Dedicated onboarding page
@dashboard_bp.route("/onboarding")
@login_required
def onboarding():
    if session.get("onboarding_complete"):
        from flask import redirect, url_for
        return redirect(url_for("dashboard.home"))
    return render_template("onboarding.html")


@dashboard_bp.route("/analyze")
@login_required
def analyze():
    """Stock analysis page"""
    return render_template("index.html")


@dashboard_bp.route("/transparency")
@login_required
def transparency():
    """Transparency & Methodology page"""
    return render_template("transparency.html")


# =====================================================================
# API: Portfolio Dashboard (Option A)
# =====================================================================
@dashboard_bp.route("/api/dashboard/portfolio", methods=["GET"])
@login_required
def api_portfolio():
    """Get portfolio dashboard: total value, daily change, top performers."""
    user_email = session.get("user_email")

    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503

    try:
        print(f"🔍 Fetching portfolio for user: {user_email}")
        response = supabase.table("watchlist").select("tickers").eq("email", user_email).execute()
        print(f"✅ Response data: {response.data}")
        tickers = []
        if response.data and len(response.data) > 0:
            tickers = response.data[0].get("tickers", [])
        print(f"✅ Tickers found: {tickers}")

        if not tickers:
            return jsonify({
                "total_value": 0,
                "daily_change": 0,
                "daily_change_pct": 0,
                "holdings_count": 0,
                "top_performers": [],
                "bottom_performers": []
            }), 200

        tickers = list(set(tickers))

        try:
            data = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
            if data is None or data.empty or len(data) < 2:
                raise ValueError("Insufficient price data")
            close_df = _normalize_close(data, tickers)
        except Exception as e:
            print(f"⚠️ Price fetch error: {e}")
            return jsonify({
                "total_value": 0,
                "daily_change": 0,
                "daily_change_pct": 0,
                "holdings_count": len(tickers),
                "top_performers": [],
                "bottom_performers": [],
                "error": "Price data unavailable (API limit or network error). Try again later."
            }), 200

        current_prices = close_df.iloc[-1]
        prev_closes = close_df.iloc[-2]

        total_value = 0
        total_prev_value = 0
        performers = []

        for ticker in tickers:
            try:
                price = float(current_prices.get(ticker, 0) or 0)
                prev = float(prev_closes.get(ticker, 0) or 0)

                change = price - prev
                change_pct = (change / prev * 100) if prev > 0 else 0

                total_value += price
                total_prev_value += prev

                performers.append({
                    "ticker": ticker,
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2)
                })
            except Exception:
                continue

        performers.sort(key=lambda x: x["change_pct"], reverse=True)
        top_performers = performers[:3]
        bottom_performers = performers[-3:] if len(performers) > 3 else []

        daily_change = total_value - total_prev_value
        daily_change_pct = (daily_change / total_prev_value * 100) if total_prev_value > 0 else 0

        return jsonify({
            "total_value": round(total_value, 2),
            "daily_change": round(daily_change, 2),
            "daily_change_pct": round(daily_change_pct, 2),
            "holdings_count": len(tickers),
            "top_performers": top_performers,
            "bottom_performers": bottom_performers,
            "last_updated": datetime.now().isoformat()
        }), 200

    except Exception as e:
        import traceback
        print(f"❌ Portfolio error: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "debug": traceback.format_exc()}), 500


# =====================================================================
# API: Watchlist Summary (Option B)
# =====================================================================
@dashboard_bp.route("/api/dashboard/watchlist-summary", methods=["GET"])
@login_required
def api_watchlist_summary():
    """Get watchlist summary: all stocks with live prices."""
    user_email = session.get("user_email")

    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503

    try:
        print(f"🔍 Fetching watchlist for user: {user_email}")
        response = supabase.table("watchlist").select("tickers, created_at").eq("email", user_email).execute()
        print(f"✅ Response data: {response.data}")
        tickers = []
        added_at = None
        if response.data and len(response.data) > 0:
            tickers = response.data[0].get("tickers", [])
            added_at = response.data[0].get("created_at")
        print(f"✅ Tickers found: {tickers}")

        if not tickers:
            return jsonify({
                "total_stocks": 0,
                "stocks": [],
                "last_updated": datetime.now().isoformat()
            }), 200

        try:
            data = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
            if data.empty or len(data) < 2:
                raise ValueError("Insufficient price data")
            close_df = _normalize_close(data, tickers)
        except Exception:
            return jsonify({
                "total_stocks": len(tickers),
                "stocks": [{"ticker": t, "price": 0, "change_pct": 0, "added_at": added_at, "direction": "neutral"} for t in tickers],
                "last_updated": datetime.now().isoformat()
            }), 200

        current_prices = close_df.iloc[-1]
        prev_closes = close_df.iloc[-2]

        stocks = []
        for ticker in tickers:
            try:
                price = float(current_prices.get(ticker, 0) or 0)
                prev = float(prev_closes.get(ticker, 0) or 0)

                change_pct = ((price - prev) / prev * 100) if prev > 0 else 0

                stocks.append({
                    "ticker": ticker,
                    "price": round(price, 2),
                    "change_pct": round(change_pct, 2),
                    "added_at": added_at,
                    "direction": "up" if change_pct >= 0 else "down"
                })
            except Exception:
                stocks.append({
                    "ticker": ticker,
                    "price": 0,
                    "change_pct": 0,
                    "added_at": added_at,
                    "direction": "neutral"
                })

        stocks.sort(key=lambda x: x["change_pct"], reverse=True)

        return jsonify({
            "total_stocks": len(stocks),
            "stocks": stocks,
            "last_updated": datetime.now().isoformat()
        }), 200

    except Exception as e:
        import traceback
        print(f"❌ Watchlist summary error: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "debug": traceback.format_exc()}), 500


# =====================================================================
# API: Market Summary (Option C)
# =====================================================================
@dashboard_bp.route("/api/dashboard/market-summary", methods=["GET"])
def api_market_summary():
    """Get market summary: S&P 500, VIX, market context."""
    try:
        sp500 = yf.Ticker("^GSPC")
        vix = yf.Ticker("^VIX")

        sp500_data = sp500.history(period="1d")
        vix_data = vix.history(period="1d")

        if sp500_data.empty or vix_data.empty:
            return jsonify({
                "sp500_price": 0,
                "sp500_change_pct": 0,
                "vix_value": 0,
                "market_sentiment": "unknown",
                "trend": "neutral"
            }), 200

        sp500_price = sp500_data["Close"].iloc[-1]
        sp500_open = sp500_data["Open"].iloc[-1]
        sp500_change = sp500_price - sp500_open
        sp500_change_pct = (sp500_change / sp500_open * 100) if sp500_open > 0 else 0

        vix_price = vix_data["Close"].iloc[-1]

        if vix_price < 15:
            sentiment = "Calm 😊"
            trend = "bullish"
        elif vix_price < 20:
            sentiment = "Normal 😐"
            trend = "neutral"
        elif vix_price < 30:
            sentiment = "Nervous 😟"
            trend = "bearish"
        else:
            sentiment = "Fearful 😨"
            trend = "very_bearish"

        return jsonify({
            "sp500_price": round(sp500_price, 2),
            "sp500_change": round(sp500_change, 2),
            "sp500_change_pct": round(sp500_change_pct, 2),
            "vix_value": round(vix_price, 2),
            "market_sentiment": sentiment,
            "trend": trend,
            "timestamp": datetime.now().isoformat()
        }), 200

    except Exception as e:
        print(f"❌ Market summary error: {e}")
        return jsonify({
            "sp500_price": 0,
            "sp500_change_pct": 0,
            "vix_value": 0,
            "market_sentiment": "unknown",
            "trend": "neutral",
            "error": str(e)
        }), 200

# =====================================================================
# Onboarding API
# =====================================================================
@dashboard_bp.route("/api/onboarding", methods=["POST"])
@login_required
def api_onboarding():
    data = request.get_json() or {}
    risk = data.get("risk")
    sectors = data.get("sectors")
    horizon = data.get("horizon")

    if risk and risk not in VALID_RISKS:
        return jsonify({"error": f"Invalid risk level '{risk}'. Must be one of: {', '.join(VALID_RISKS)}"}), 400
    if horizon and horizon not in VALID_HORIZONS:
        return jsonify({"error": f"Invalid horizon '{horizon}'. Must be one of: {', '.join(VALID_HORIZONS)}"}), 400
    if sectors is not None and not isinstance(sectors, list):
        return jsonify({"error": "sectors must be a list"}), 400

    session["onboarding_complete"] = True
    session["onboarding_risk"] = risk
    session["onboarding_sectors"] = sectors
    session["onboarding_horizon"] = horizon
    return jsonify({"ok": True})

# =====================================================================
# API: Watchlist Add (called from the analyze/index page Track button)
# =====================================================================
@dashboard_bp.route("/api/dashboard/watchlist-add", methods=["POST"])
@login_required
def api_watchlist_add():
    """Add a ticker to the user's default watchlist."""
    user_email = session.get("user_email")

    if not supabase:
        return jsonify({"ok": False, "error": "Supabase not configured"}), 503

    data = request.get_json() or {}
    ticker = data.get("ticker", "").upper().strip()
    if not ticker:
        return jsonify({"ok": False, "error": "ticker is required"}), 400

    try:
        response = supabase.table("watchlist").select("id, tickers").eq("email", user_email).execute()

        if response.data and len(response.data) > 0:
            row = response.data[0]
            tickers = row.get("tickers") or []
            if ticker not in tickers:
                tickers.append(ticker)
                supabase.table("watchlist").update({"tickers": tickers}).eq("id", row["id"]).execute()
        else:
            supabase.table("watchlist").insert({"email": user_email, "tickers": [ticker]}).execute()

        return jsonify({"ok": True, "message": f"{ticker} added to watchlist"}), 200
    except Exception as e:
        import traceback
        print(f"❌ watchlist-add error: {e}\n{traceback.format_exc()}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =====================================================================
# API: Portfolio Health
# =====================================================================
@dashboard_bp.route("/api/dashboard/portfolio-health", methods=["GET"])
@login_required
def api_portfolio_health():
    user_email = session.get("user_email")
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    try:
        response = supabase.table("watchlist").select("tickers").eq("email", user_email).execute()
        tickers = []
        if response.data and len(response.data) > 0:
            tickers = response.data[0].get("tickers", [])
        tickers = list(set(tickers))

        if not tickers:
            return jsonify({
                "summary": "No holdings.",
                "diversification": "-",
                "correlation": "-",
                "score": "-",
                "last_updated": datetime.now().isoformat()
            })

        sector_counts = {}
        sector_map = {}
        for t in tickers:
            try:
                info = yf.Ticker(t).info
                sector = info.get("sector", "Unknown")
            except Exception:
                sector = "Unknown"
            sector_map[t] = sector
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        top_sector = max(sector_counts, key=sector_counts.get)
        top_sector_pct = sector_counts[top_sector] / len(tickers)
        diversification = f"{int(top_sector_pct*100)}% in {top_sector}"

        high_corr = (sector_counts.get("Technology", 0) >= 2)
        correlation = "High (many tech stocks)" if high_corr else "Normal"

        if top_sector_pct > 0.7 or high_corr:
            score = "⚠️ Risky"
            summary = "Your portfolio is concentrated. Diversify for lower risk."
        else:
            score = "✅ Healthy"
            summary = "Your portfolio is reasonably diversified."

        return jsonify({
            "summary": summary,
            "diversification": diversification,
            "correlation": correlation,
            "score": score,
            "last_updated": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": f"Portfolio health error: {e}", "last_updated": datetime.now().isoformat()})

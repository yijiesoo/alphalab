"""
Dashboard routes: Home, Analyze, and dashboard API endpoints
"""
from flask import Blueprint, render_template, session, jsonify, request
from datetime import datetime
import yfinance as yf

# Import optimized batch fetching
try:
    from flask_app.ticker_fetch import fetch_ticker_prices, fetch_tickers_combined
except ImportError:
    from ticker_fetch import fetch_ticker_prices, fetch_tickers_combined

# Import retry wrapper from yfinance utilities
try:
    from flask_app.yfinance_utils import yf_download_with_retry
except ImportError:
    from yfinance_utils import yf_download_with_retry

try:
    from flask_app.routes import login_required
    from flask_app.config import Config
except ImportError:
    from routes import login_required
    from config import Config

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__)

# Initialize cache and supabase globally
_cache = {}
supabase = None


def init_supabase(sb):
    """Initialize supabase instance"""
    global supabase
    supabase = sb


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
    return render_template("home.html")


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
        # Get tickers from watchlist (stored as array in 'tickers' column)
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
        
        # Fetch prices using optimized batch function (with caching + dedup)
        try:
            prices = fetch_ticker_prices(tickers, period="5d", logger=None)
            if not prices:
                raise ValueError("No price data available")
        except Exception as e:
            print(f"❌ Price fetch error: {e}")
            return jsonify({
                "total_value": 0,
                "daily_change": 0,
                "daily_change_pct": 0,
                "holdings_count": len(tickers),
                "top_performers": [],
                "bottom_performers": []
            }), 200
        
        # Calculate portfolio metrics
        total_current = sum(p["current_price"] for p in prices.values())
        total_prev = sum(p["current_price"] / (1 + p["pct_change"]/100) for p in prices.values() if p["pct_change"] != 0)
        total_change = total_current - total_prev
        total_change_pct = (total_change / total_prev * 100) if total_prev > 0 else 0
        
        performers = []
        for ticker, price_data in prices.items():
            performers.append({
                "ticker": ticker,
                "price": price_data["current_price"],
                "change_pct": price_data["pct_change"]
            })
        
        # Sort by change
        performers.sort(key=lambda x: x["change_pct"], reverse=True)
        top_performers = performers[:3]
        bottom_performers = performers[-3:] if len(performers) > 3 else []
        
        return jsonify({
            "total_value": round(total_current, 2),
            "daily_change": round(total_change, 2),
            "daily_change_pct": round(total_change_pct, 2),
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
        # Get watchlist tickers (stored as array in 'tickers' column)
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
        
        # Fetch prices using optimized batch function (with caching + dedup)
        try:
            prices = fetch_ticker_prices(tickers, period="5d", logger=None)
            if not prices:
                raise ValueError("No price data available")
        except Exception as e:
            print(f"❌ Price fetch error: {e}")
            return jsonify({
                "total_stocks": len(tickers),
                "stocks": [{"ticker": t, "price": 0, "change_pct": 0, "added_at": added_at, "direction": "neutral"} for t in tickers],
                "last_updated": datetime.now().isoformat()
            }), 200
        
        stocks = []
        for ticker, price_data in prices.items():
            stocks.append({
                "ticker": ticker,
                "price": price_data["current_price"],
                "change_pct": price_data["pct_change"],
                "added_at": added_at,
                "direction": "up" if price_data["pct_change"] >= 0 else "down"
            })
        
        # Sort by change (best performers first)
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
        # Fetch market indices using our optimized function (avoids quoteSummary)
        indices_data = fetch_ticker_prices(["^GSPC", "^VIX"], period="1d", logger=None)
        
        if not indices_data or len(indices_data) < 2:
            raise ValueError("Could not fetch market data")
        
        # Extract market indices data (pre-calculated by batch fetcher)
        sp500_price = indices_data.get("^GSPC", {}).get("current_price", 0)
        sp500_change_pct = indices_data.get("^GSPC", {}).get("pct_change", 0)
        vix_price = indices_data.get("^VIX", {}).get("current_price", 0)
        
        if sp500_price == 0 or vix_price == 0:
            return jsonify({
                "sp500_price": 0,
                "sp500_change_pct": 0,
                "vix_value": 0,
                "market_sentiment": "unknown",
                "trend": "neutral"
            }), 200
        
        # Determine market sentiment based on VIX
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

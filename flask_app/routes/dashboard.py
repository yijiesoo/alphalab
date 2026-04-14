"""
Dashboard routes: Home, Analyze, and dashboard API endpoints
"""
from flask import Blueprint, render_template, session, jsonify, request
from datetime import datetime
import yfinance as yf
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
        
        # Remove duplicates
        tickers = list(set(tickers))
        
        # Fetch prices: use 5d period so we always have at least 2 trading days
        # and can compute close-to-close daily change (not intraday open-to-close).
        try:
            data = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
            if data.empty or len(data) < 2:
                raise ValueError("Insufficient price data")
            if len(tickers) == 1:
                current_price = data["Close"].iloc[-1]
                prev_close = data["Close"].iloc[-2]  # yesterday's close
            else:
                current_price = data["Close"].iloc[-1]
                prev_close = data["Close"].iloc[-2]  # yesterday's close
        except Exception:
            return jsonify({
                "total_value": 0,
                "daily_change": 0,
                "daily_change_pct": 0,
                "holdings_count": len(tickers),
                "top_performers": [],
                "bottom_performers": []
            }), 200
        
        # Calculate portfolio metrics
        total_value = 0
        total_prev_value = 0
        performers = []
        
        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    price = current_price
                    prev = prev_close
                else:
                    price = current_price[ticker]
                    prev = prev_close[ticker]
                
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
        
        # Sort by change
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
        
        # Fetch prices: 5d period to guarantee at least 2 trading days for
        # close-to-close daily change calculation.
        try:
            data = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
            if data.empty or len(data) < 2:
                raise ValueError("Insufficient price data")
            current_price = data["Close"].iloc[-1]
            prev_close = data["Close"].iloc[-2]  # yesterday's close (not today's open)
        except Exception:
            return jsonify({
                "total_stocks": len(tickers),
                "stocks": [{"ticker": t, "price": 0, "change_pct": 0, "added_at": added_at, "direction": "neutral"} for t in tickers],
                "last_updated": datetime.now().isoformat()
            }), 200
        
        stocks = []
        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    price = current_price
                    prev = prev_close
                else:
                    price = current_price[ticker]
                    prev = prev_close[ticker]
                
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
        # Fetch market indices
        sp500 = yf.Ticker("^GSPC")
        vix = yf.Ticker("^VIX")
        
        # Get latest data
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

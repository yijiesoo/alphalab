"""
Multiple watchlists and portfolio tracking for alphalab.
Allows users to create multiple watchlists and track portfolio performance.
"""

from datetime import datetime
from typing import Dict, List, Optional

import yfinance as yf


def get_user_watchlists(supabase, email: str) -> List[Dict]:
    """Get all watchlists for a user."""
    try:
        response = supabase.table("watchlists").select("*").eq("email", email).execute()
        return response.data or []
    except Exception as e:
        print(f"❌ Error fetching watchlists for {email}: {e}")
        return []


def create_watchlist(supabase, email: str, name: str) -> Optional[Dict]:
    """Create a new watchlist for user."""
    try:
        response = supabase.table("watchlists").insert({
            "email": email,
            "name": name,
            "tickers": []
        }).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"❌ Error creating watchlist: {e}")
        return None


def delete_watchlist(supabase, watchlist_id: str) -> bool:
    """Delete a watchlist."""
    try:
        supabase.table("watchlists").delete().eq("id", watchlist_id).execute()
        return True
    except Exception as e:
        print(f"❌ Error deleting watchlist: {e}")
        return False


def add_ticker_to_watchlist(supabase, watchlist_id: str, ticker: str) -> bool:
    """Add a ticker to a watchlist."""
    try:
        # Get current tickers
        response = supabase.table("watchlists").select("tickers").eq("id", watchlist_id).single().execute()
        tickers = response.data.get("tickers", []) if response.data else []

        # Add if not present
        if ticker not in tickers:
            tickers.append(ticker)
            supabase.table("watchlists").update({
                "tickers": tickers,
                "updated_at": datetime.now().isoformat()
            }).eq("id", watchlist_id).execute()

        return True
    except Exception as e:
        print(f"❌ Error adding ticker: {e}")
        return False


def remove_ticker_from_watchlist(supabase, watchlist_id: str, ticker: str) -> bool:
    """Remove a ticker from a watchlist."""
    try:
        # Get current tickers
        response = supabase.table("watchlists").select("tickers").eq("id", watchlist_id).single().execute()
        tickers = response.data.get("tickers", []) if response.data else []

        # Remove if present
        if ticker in tickers:
            tickers.remove(ticker)
            supabase.table("watchlists").update({
                "tickers": tickers,
                "updated_at": datetime.now().isoformat()
            }).eq("id", watchlist_id).execute()

        return True
    except Exception as e:
        print(f"❌ Error removing ticker: {e}")
        return False


def calculate_portfolio_performance(tickers: List[str], period: str = "1y") -> Dict:
    """
    Calculate portfolio performance metrics.

    Returns:
        - total_return: Overall return %
        - stocks: Individual stock returns
        - best_performer: Best performing stock
        - worst_performer: Worst performing stock
        - avg_return: Average return across stocks
    """
    if not tickers:
        return {
            "total_return": 0,
            "stocks": {},
            "best_performer": None,
            "worst_performer": None,
            "avg_return": 0
        }

    try:
        # Download data with proper error handling
        data = yf.download(tickers, period=period, progress=False, threads=True)

        if data is None or data.empty:
            raise ValueError("No data returned from yfinance")

        # Handle single ticker vs multiple tickers
        if len(tickers) == 1:
            # Single ticker returns Series, not DataFrame
            if "Adj Close" not in data.columns:
                adj_close = data
            else:
                adj_close = data["Adj Close"]

            first_price = adj_close.iloc[0]
            last_price = adj_close.iloc[-1]
            return_pct = ((last_price - first_price) / first_price) * 100
            returns = {tickers[0]: return_pct}
        else:
            # Multiple tickers - get Adj Close column
            adj_close = data.get("Adj Close", data)
            if adj_close.empty:
                raise ValueError("No Adj Close data available")

            returns = {}
            for ticker in tickers:
                if ticker in adj_close.columns:
                    first_price = adj_close[ticker].iloc[0]
                    last_price = adj_close[ticker].iloc[-1]
                    return_pct = ((last_price - first_price) / first_price) * 100
                    returns[ticker] = return_pct

        # Calculate metrics
        returns_list = list(returns.values())
        avg_return = sum(returns_list) / len(returns_list) if returns_list else 0
        best_ticker = max(returns, key=returns.get) if returns else None
        worst_ticker = min(returns, key=returns.get) if returns else None

        return {
            "total_return": round(avg_return, 2),
            "stocks": {k: round(v, 2) for k, v in returns.items()},
            "best_performer": {
                "ticker": best_ticker,
                "return": round(returns.get(best_ticker, 0), 2)
            } if best_ticker else None,
            "worst_performer": {
                "ticker": worst_ticker,
                "return": round(returns.get(worst_ticker, 0), 2)
            } if worst_ticker else None,
            "avg_return": round(avg_return, 2),
            "period": period
        }
    except Exception as e:
        print(f"❌ Error calculating portfolio performance: {e}")
        return {
            "total_return": 0,
            "stocks": {},
            "best_performer": None,
            "worst_performer": None,
            "avg_return": 0
        }


def get_current_prices(tickers: List[str]) -> Dict[str, float]:
    """Get current prices for tickers."""
    try:
        data = yf.download(tickers, period="1d", progress=False, threads=True)

        if data is None or data.empty:
            return {}

        # Handle single ticker vs multiple
        if len(tickers) == 1:
            if "Adj Close" in data.columns:
                price = float(data["Adj Close"].iloc[-1])
            else:
                price = float(data.iloc[-1])
            return {tickers[0]: price}
        else:
            adj_close = data.get("Adj Close", data)
            return {ticker: float(adj_close[ticker].iloc[-1]) for ticker in tickers if ticker in adj_close.columns}
    except Exception as e:
        print(f"❌ Error fetching prices: {e}")
        return {}


def calculate_portfolio_value(watchlist: Dict, quantities: Optional[Dict] = None) -> Dict:
    """
    Calculate total portfolio value.

    Args:
        watchlist: Watchlist dict with tickers
        quantities: Dict mapping ticker -> quantity owned (optional)

    Returns:
        - total_value: Total portfolio value
        - stocks: Per-stock breakdown
        - average_price: Average cost per share
    """
    tickers = watchlist.get("tickers", [])

    if not tickers:
        return {
            "total_value": 0,
            "stocks": {},
            "average_price": 0
        }

    try:
        prices = get_current_prices(tickers)

        stocks_breakdown = {}
        total_value = 0

        for ticker in tickers:
            price = prices.get(ticker, 0)
            qty = quantities.get(ticker, 1) if quantities else 1
            value = price * qty

            stocks_breakdown[ticker] = {
                "price": price,
                "quantity": qty,
                "value": value
            }
            total_value += value

        avg_price = total_value / len(tickers) if tickers else 0

        return {
            "total_value": round(total_value, 2),
            "stocks": stocks_breakdown,
            "average_price": round(avg_price, 2),
            "stock_count": len(tickers)
        }
    except Exception as e:
        print(f"❌ Error calculating portfolio value: {e}")
        return {
            "total_value": 0,
            "stocks": {},
            "average_price": 0
        }

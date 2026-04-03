"""
scorer.py — per-ticker analysis for the /api/analyze endpoint.

Returns lightweight metadata for a single equity ticker: whether it is
available in yfinance, the most-recent adjusted close price, and how many
trading days of history were loaded.  This is intentionally minimal; extend
it later to include factor scores, backtest metrics, etc.
"""

from src.data import download_prices


def analyze_ticker(ticker: str) -> dict:
    """
    Return a lightweight analysis dict for a single ticker.

    Parameters
    ----------
    ticker : str
        Equity ticker symbol, e.g. ``"NVDA"``.

    Returns
    -------
    dict with keys:
        ticker       : the (uppercased) ticker symbol requested
        in_universe  : bool — True if price data was found
        latest_price : float or None — most-recent adjusted close price
        note         : human-readable summary string
    """
    ticker = ticker.upper().strip()

    try:
        prices = download_prices(tickers=[ticker], start="2020-01-01")
    except Exception as exc:
        return {
            "ticker": ticker,
            "in_universe": False,
            "latest_price": None,
            "note": f"Error fetching data for {ticker}: {exc}",
        }

    if ticker not in prices.columns or prices[ticker].dropna().empty:
        return {
            "ticker": ticker,
            "in_universe": False,
            "latest_price": None,
            "note": f"No price data found for {ticker}.",
        }

    series = prices[ticker].dropna()
    latest_price = float(series.iloc[-1])
    n_days = len(series)

    return {
        "ticker": ticker,
        "in_universe": True,
        "latest_price": round(latest_price, 4),
        "note": (
            f"Data available for {ticker}. "
            f"{n_days} trading days loaded "
            f"(from {series.index[0].date()} to {series.index[-1].date()})."
        ),
    }

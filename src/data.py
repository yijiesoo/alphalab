"""
data.py — download, clean, and align OHLCV price data.

KEY CONCEPT: We use *adjusted close* prices, which account for dividends
and stock splits. Using unadjusted prices would create fake signals at
split dates (e.g. a 2-for-1 split looks like a -50% crash without adjustment).

LIMITATION: yfinance only returns *currently listed* tickers. If a stock
was delisted between 2015 and today, it will be missing from results.
This is called survivorship bias — we are implicitly overweighting
companies that survived. Document this clearly in your README.
"""

import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# Default universe — S&P 500 large caps, manually curated starter list.
# Replace or extend this list to change your investment universe.
# Later: load from a CSV so you can swap universes without editing code.
# ---------------------------------------------------------------------------
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "BRK-B", "LLY",
    "JPM", "V", "UNH", "XOM", "TSLA", "MA", "JNJ", "PG", "HD",
    "MRK", "AVGO", "CVX", "ABBV", "KO", "PEP", "COST", "WMT",
    "BAC", "MCD", "CRM", "NFLX", "AMD", "TMO", "LIN", "ACN", "ABT",
    "CSCO", "DHR", "DIS", "VZ", "ADBE", "WFC", "TXN", "NEE", "PM",
    "ORCL", "RTX", "AMGN", "COP", "IBM", "HON", "QCOM",
]


def download_prices(
    tickers: list[str] = DEFAULT_TICKERS,
    start: str = "2015-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """
    Download adjusted close prices for a list of tickers.

    Returns a DataFrame where:
    - rows = trading days (DatetimeIndex)
    - columns = ticker symbols
    - values = adjusted close price

    Parameters
    ----------
    tickers : list of ticker strings
    start   : ISO date string, e.g. "2015-01-01"
    end     : ISO date string or None (defaults to today)

    IMPORTANT: We use auto_adjust=True so yfinance returns prices that
    are already adjusted for splits and dividends. This means prices for
    older dates will look "wrong" compared to historical quotes — that's
    correct behaviour.
    """
    raw = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=True,   # returns adjusted OHLCV directly
        progress=False,
    )

    # yfinance returns a MultiIndex: (price_type, ticker)
    # We only want the Close column
    prices: pd.DataFrame = raw["Close"].copy()

    prices = _clean_prices(prices)
    return prices


def _clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Apply data quality rules to raw price matrix.

    Rules applied (in order):
    1. Drop tickers that have *no* data at all (e.g. download failed)
    2. Forward-fill small gaps (up to 5 trading days) — handles public holidays
       where one exchange is closed but others are not.
    3. Drop tickers still missing >10% of observations after forward-fill —
       likely a data quality issue, not a genuine trading gap.

    WHY forward-fill and not interpolate?
    We only know the last known price at the time, not the future price.
    Forward-filling simulates "last price available" which is what you'd
    see on a real trading terminal. Interpolating would be look-ahead bias.
    """
    # Rule 1: drop entirely empty columns
    prices = prices.dropna(axis=1, how="all")

    # Rule 2: forward-fill short gaps (max 5 consecutive NaN days)
    prices = prices.ffill(limit=5)

    # Rule 3: drop tickers with >10% missing after forward-fill
    missing_frac = prices.isna().mean()
    too_sparse = missing_frac[missing_frac > 0.10].index.tolist()
    if too_sparse:
        print(f"[data] Dropping {len(too_sparse)} tickers with >10% missing: {too_sparse}")
    prices = prices.drop(columns=too_sparse)

    return prices


def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute simple (arithmetic) daily returns from price levels.

    Return_t = (Price_t - Price_{t-1}) / Price_{t-1}

    WHY simple returns (not log returns)?
    Simple returns are additive across assets (portfolio return = weighted
    sum of asset returns), which makes portfolio construction easier.
    Log returns are additive across time, which is useful for compounding.
    We use simple returns for cross-sectional factor work.
    """
    return prices.pct_change()


def get_rebalance_dates(prices: pd.DataFrame, frequency: str = "MS") -> pd.DatetimeIndex:
    """
    Generate rebalance dates from the price index.

    Parameters
    ----------
    prices    : price DataFrame with DatetimeIndex
    frequency : pandas offset alias
                "MS" = month start (default)
                "ME" = month end
                "QS" = quarter start

    We intersect the desired calendar dates with actual trading days
    so we never try to trade on a weekend or holiday.
    """
    # Generate ideal calendar dates
    calendar_dates = pd.date_range(
        start=prices.index[0],
        end=prices.index[-1],
        freq=frequency,
    )
    # Keep only dates that exist in the actual price index (trading days)
    trading_days = prices.index
    rebalance_dates = trading_days[trading_days.isin(calendar_dates)]
    return rebalance_dates


if __name__ == "__main__":
    # Quick smoke test — run this file directly to check data downloads
    print("Downloading prices for default universe...")
    prices = download_prices(start="2018-01-01")
    print(f"Shape: {prices.shape}")
    print(f"Date range: {prices.index[0].date()} to {prices.index[-1].date()}")
    print(f"Tickers: {list(prices.columns[:5])}...")
    print(prices.tail(3))

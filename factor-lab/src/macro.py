import yfinance as yf

SECTOR_ETFS = {
    "tech": "XLK",
    "energy": "XLE",
    "financials": "XLF",
    "healthcare": "XLV",
    "consumer": "XLY",
    "utilities": "XLU",
}


def get_macro_context(ticker: str) -> dict:
    """
    Returns a plain-English macro snapshot relevant to the given ticker.
    Includes:
    - 10Y yield (interest rate environment)
    - S&P 500 momentum (broad market trend)
    - Sector momentum (relative to sector ETF)
    - Bond/equity yield spread (valuation pressure)
    
    Note: VIX calculation is commented out for now.
    """
    # vix = _get_latest_price("^VIX")  # COMMENTED OUT: VIX disabled
    vix = None  # VIX disabled
    yield_10y = _get_latest_price("^TNX")  # CBOE 10Y yield index
    sp500_momentum = _get_sp500_momentum()  # Broad market trend
    sector = _guess_sector(ticker)
    sector_signal = _sector_momentum(sector)
    yield_risk_free = _get_latest_price("^TNX")  # 10Y as risk-free rate

    return {
        # "vix": vix,  # COMMENTED OUT: VIX disabled
        "vix": None,  # VIX disabled
        # "vix_label": _vix_label(vix),  # COMMENTED OUT: VIX disabled
        "vix_label": "N/A",  # VIX disabled
        "yield_10y": yield_10y,
        "yield_label": _yield_label(yield_10y),
        "sp500_momentum": sp500_momentum,
        "sp500_label": _sp500_momentum_label(sp500_momentum),
        "sector": sector,
        "sector_signal": sector_signal,
        "summary": _build_summary(vix, yield_10y, sector, sector_signal, sp500_momentum),
    }


def _get_latest_price(symbol: str) -> float:
    try:
        data = yf.download(symbol, period="5d", progress=False, auto_adjust=True)
        close_price = data["Close"].dropna().iloc[-1]
        return round(float(close_price.item()) if hasattr(close_price, 'item') else float(close_price), 2)
    except Exception:
        return None


def _get_sp500_momentum() -> str:
    """Get S&P 500 3-month momentum to assess broad market trend."""
    try:
        data = yf.download("^GSPC", period="3mo", progress=False, auto_adjust=True)
        closes = data["Close"].dropna()
        ret = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]
        if ret > 0.08:
            return "strong"
        elif ret > 0.03:
            return "positive"
        elif ret > -0.03:
            return "neutral"
        elif ret > -0.08:
            return "slightly negative"
        else:
            return "weak"
    except Exception:
        # Try alternative S&P 500 ticker
        try:
            data = yf.download("SPY", period="3mo", progress=False, auto_adjust=True)
            closes = data["Close"].dropna()
            ret = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]
            if ret > 0.08:
                return "strong"
            elif ret > 0.03:
                return "positive"
            elif ret > -0.03:
                return "neutral"
            elif ret > -0.08:
                return "slightly negative"
            else:
                return "weak"
        except Exception:
            return "unavailable"


def _sp500_momentum_label(momentum: str) -> str:
    """Explain S&P 500 momentum impact."""
    labels = {
        "strong": "Bull market — favorable for equities",
        "positive": "Uptrend — generally positive sentiment",
        "neutral": "Sideways — no clear trend",
        "slightly negative": "Weakness — caution warranted",
        "weak": "Downtrend — risk-off environment",
        "unavailable": "Data unavailable",
    }
    return labels.get(momentum, "Unknown")


def _sector_momentum(sector: str) -> str:
    etf = SECTOR_ETFS.get(sector)
    if not etf:
        return "neutral"
    try:
        data = yf.download(etf, period="3mo", progress=False, auto_adjust=True)
        closes = data["Close"].dropna()
        ret = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]
        if ret > 0.05:
            return "strong"
        elif ret > 0:
            return "positive"
        elif ret > -0.05:
            return "slightly negative"
        else:
            return "weak"
    except Exception:
        return "unavailable"


def _guess_sector(ticker: str) -> str:
    """
    Lightweight sector lookup using yfinance ticker info.
    Falls back to 'unknown' gracefully.
    """
    try:
        info = yf.Ticker(ticker).info
        sector_raw = info.get("sector", "").lower()
        mapping = {
            "technology": "tech",
            "energy": "energy",
            "financial": "financials",
            "healthcare": "healthcare",
            "consumer cyclical": "consumer",
            "utilities": "utilities",
        }
        for key, val in mapping.items():
            if key in sector_raw:
                return val
        return "unknown"
    except Exception:
        return "unknown"


def _vix_label(vix) -> str:
    if vix is None:
        return "unavailable"
    if vix < 15:
        return "calm — low fear in the market"
    elif vix < 25:
        return "moderate — normal conditions"
    elif vix < 35:
        return "elevated — market is nervous"
    else:
        return "high — significant market stress"


def _yield_label(y) -> str:
    if y is None:
        return "unavailable"
    if y < 3.5:
        return "low — supportive for growth stocks"
    elif y < 4.5:
        return "moderate — neutral environment"
    else:
        return "high — pressure on valuations"


def _build_summary(vix, yield_10y, sector, sector_signal, sp500_momentum) -> str:
    parts = []
    
    # Market regime (S&P 500)
    if sp500_momentum != "unavailable":
        parts.append(f"Broad market is {sp500_momentum}.")
    
    # Interest rate environment
    if yield_10y is not None:
        parts.append(f"10Y yield at {yield_10y}% — {_yield_label(yield_10y)}.")
    
    # Sector trend
    if sector != "unknown":
        parts.append(f"{sector.capitalize()} sector is {sector_signal} (3-mo trend).")
    
    # Decision context
    if parts:
        parts.append("Use this with momentum & sentiment for decisions.")
    
    return " ".join(parts) if parts else "Macro data unavailable."

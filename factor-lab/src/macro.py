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
    Pulls VIX, 10Y yield, and sector ETF momentum from yfinance.
    """
    vix = _get_latest_price("^VIX")
    yield_10y = _get_latest_price("^TNX")  # CBOE 10Y yield index
    sector = _guess_sector(ticker)
    sector_signal = _sector_momentum(sector)

    return {
        "vix": vix,
        "vix_label": _vix_label(vix),
        "yield_10y": yield_10y,
        "yield_label": _yield_label(yield_10y),
        "sector": sector,
        "sector_signal": sector_signal,
        "summary": _build_summary(vix, yield_10y, sector, sector_signal),
    }


def _get_latest_price(symbol: str) -> float:
    try:
        data = yf.download(symbol, period="5d", progress=False, auto_adjust=True)
        return round(float(data["Close"].dropna().iloc[-1]), 2)
    except Exception:
        return None


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


def _build_summary(vix, yield_10y, sector, sector_signal) -> str:
    parts = []
    if vix is not None:
        parts.append(f"Market volatility (VIX {vix}) is {_vix_label(vix)}.")
    if yield_10y is not None:
        parts.append(f"10Y yield at {yield_10y}% — {_yield_label(yield_10y)}.")
    if sector != "unknown":
        parts.append(
            f"{sector.capitalize()} sector momentum is {sector_signal} over the past 3 months."
        )
    return " ".join(parts) if parts else "Macro data unavailable."

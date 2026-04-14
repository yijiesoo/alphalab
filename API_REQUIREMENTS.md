# AlphaLab Data API Requirements Analysis

## A) DATA TYPES NEEDED

### Backtest / Analysis (Factor-Lab)
- **EOD (End-of-Day) data ONLY** - 1 day bars
- **Period**: 2015-01-01 to present (11+ years historical)
- **Data Points**: Close price + OHLC for technical analysis
- **Adjustment**: Split + Dividend adjusted (auto_adjust=True equivalent)
- **Real-time**: NOT required - backtest is historical

### Production Dashboard
- **EOD data**: 5-day window for portfolio performance
- **Real-time / Delayed**: 15-min delayed acceptable
  - Portfolio page updates every page load (no constant streaming)
  - Watchlist updates on-demand
- **No intraday data needed** (no 1m/5m bars in current implementation)

**ANSWER A**: 
- ✅ EOD bars ONLY (1d, no intraday)
- ✅ 11+ years history (2015-01-01 to today)
- ✅ Adjusted close (splits + dividends)
- ✅ 15-min delayed acceptable (no real-time needed)
- ✅ US equities ONLY (no crypto, forex, ETFs yet)

---

## B) SCOPE / SCALE

### Universe Size
From `factor-lab/src/data.py`:
```python
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "BRK-B", "LLY",
    "JPM", "V", "UNH", "XOM", "TSLA", "MA", "JNJ", "PG", "HD",
    # ... 47 total tickers
]
```
- **Backtest**: 50 tickers (S&P 500 large caps)
- **Production**: Per-user watchlists
  - Currently: ~4 tickers per user in demo
  - Watchlist includes indices: ^GSPC, ^VIX (market context)

### Users & Scale
- **Current**: ~1 user (demo mode)
- **Projected**: Low-medium scale (startup, <100K users)
- **Multiple watchlists per user**: ~1 per user (currently)

### API Call Frequency
**Backtest**: One-time per run (triggered manually by user)
- ~50 tickers × 11 years of daily data
- Per backtest run: Single bulk historical download (1 API call ideally)

**Production Dashboard**: 
- Portfolio page: ~1-4 API calls per page load (deduplicated)
- Market summary: 2 API calls (^GSPC, ^VIX)
- Watchlist: 4 API calls (user's tickers)
- **Total per user per day**: ~20-30 API calls (conservative estimate)

**ANSWER B**:
- ✅ Backtest: 50 tickers, 11 years → 1 bulk historical download
- ✅ Production: 4-20 tickers per user per request
- ✅ Update frequency: **On-demand** (no streaming/real-time)
- ✅ ~20-30 API calls per user per day (low volume)
- ✅ Projected: <100K users eventually

---

## C) DATA QUALITY REQUIREMENTS

### Adjustments
- ✅ **MUST**: Split-adjusted prices (2-for-1 splits, etc.)
- ✅ **MUST**: Dividend-adjusted prices (yield impact)
- ✅ Current behavior: auto_adjust=True equivalent required
- ❌ **Known limitation**: Survivorship bias accepted (deleted tickers missing)

### Missing Data Handling
From `_clean_prices()` in data.py:
- ✅ Forward-fill small gaps (up to 5 trading days) for holidays
- ✅ Drop tickers with >10% missing observations
- ✅ This is handled in our ETL layer, not API requirement

### Historical Accuracy
- ✅ Must preserve historical adjusted prices (IMPORTANT)
- ✅ Must not retroactively update old prices (would break factor analysis)
- ⚠️  Survivorship bias known & documented → acceptable

**ANSWER C**:
- ✅ Split + dividend adjusted (non-negotiable)
- ✅ Historical data immutable (no retroactive adjustments)
- ✅ Survivorship bias acceptable (document it)
- ✅ Error handling: ETL layer manages gaps and bad data

---

## D) ENGINEERING CONSTRAINTS

### Must-Have Features
1. **Bulk multi-ticker endpoint** 
   - Fetch 50 tickers in 1 API call, not 50 calls
   - CRITICAL for cost optimization
   - Example: `GET /data?symbols=AAPL,NVDA,GOOG&start=2015-01-01`

2. **Long historical data** 
   - At least 11 years (2015+)
   - Most APIs support this

3. **Error handling**
   - Missing data → return what's available, not fail
   - Invalid ticker → return empty for that ticker

4. **Caching friendly**
   - Deterministic endpoints (same input = same output)
   - Our Redis layer will cache 5-min responses

### Budget Constraint
- **Target**: <$50/month
- **Reasoning**: 
  - Backtest: ~1-2 bulk downloads per day = ~50 API calls
  - Production: ~50-100 API calls per day (est. 10 users)
  - Total: ~100-150 API calls/day = ~3,000-5,000/month
  - Most paid APIs: $9-25/mo for this volume

### Cost Breakdown (Estimated)
| Provider | Free Tier | Paid Tier | Multi-ticker? | 11yr History? | Comment |
|----------|-----------|-----------|---------------|---------------|---------|
| **Polygon.io** | 5 req/min | $25/mo | ✅ Yes | ✅ Yes | **BEST CHOICE** |
| **IEX Cloud** | 100/month | $9/mo | ✅ Yes | ✅ Yes | Budget option |
| **Twelve Data** | Limited | $99/mo | ✅ Yes | ✅ Yes | Enterprise |
| **AlphaVantage** | 5 req/min | $5/mo | ⚠️ Limited | ✅ Yes | Simple |
| Yahoo Finance | Unlimited | N/A | ✅ Yes | ✅ Yes | IP-blocked in Asia! |

**ANSWER D**:
- ✅ MUST support bulk multi-ticker endpoints
- ✅ MUST support 11+ years historical data
- ✅ Budget: <$50/month
- ✅ Must handle missing tickers gracefully
- ✅ Estimated volume: ~5K API calls/month

---

## RECOMMENDATION

### Primary Choice: **Polygon.io**
**Why:**
- $25/month = well within budget
- Bulk endpoint: `GET /v2/aggs/grouped/locale/us/market/stocks/{date}` (all tickers in 1 call!)
- 11+ years of EOD data ✅
- Split/dividend adjusted ✅
- Great documentation
- Used by many trading platforms

**Cost breakdown:**
- 5,000 API calls/month = ~$0.005 per call
- Total: ~$25/month

### Backup Choice: **IEX Cloud**
**Why:**
- $9/month (cheapest paid option)
- Same features as Polygon
- Slightly less reliable uptime

### Implementation Strategy
1. Create `flask_app/data_providers/polygon_provider.py`
2. Update `ticker_fetch.py` to use Polygon instead of yfinance
3. Keep abstraction layer (still call `fetch_ticker_prices()`)
4. Add `POLYGON_API_KEY` to Railway environment
5. Test backtest with new provider
6. Deploy

**Estimated work**: 15-30 minutes

---

## Summary Table

| Aspect | Answer | Details |
|--------|--------|---------|
| **Data Type** | EOD only | 1-day bars, no intraday |
| **History** | 11+ years | 2015-01-01 to today |
| **Real-time** | 15-min OK | No streaming needed |
| **Tickers** | US equities | 50 backtest, 4-20 production |
| **Volume** | 5K calls/mo | 100-150/day |
| **Bulk API** | REQUIRED | Critical for cost |
| **Adjustments** | Split + div | Non-negotiable |
| **Budget** | <$50/mo | Polygon.io $25/mo works |
| **Recommendation** | **Polygon.io** | Best value + features |


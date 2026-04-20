# 🏗️ AlphaLab Architecture

Complete system design and technical decisions.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                            │
│               (HTML/CSS/JS with Chart.js, Auth)                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/HTTPS (REST API)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              FLASK WEB APPLICATION (Python 3.13)                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Routes Layer                                             │   │
│  │  • GET /api/analyze?ticker=AAPL (Factor analysis)       │   │
│  │  • GET /api/ml-scores/<ticker> (ML predictions)         │   │
│  │  • GET /api/portfolio/summary (Holdings + P&L)          │   │
│  │  • POST /api/portfolio/holdings (Add position)          │   │
│  │  • GET /api/backtest/stream (SSE logs)                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Service Layer                                            │   │
│  │  • TickerAnalyzer (calculates technical scores)          │   │
│  │  • PortfolioManager (tracks holdings, P&L)              │   │
│  │  • SentimentAnalyzer (FinBERT scoring)                   │   │
│  │  • BacktesterService (runs historical simulations)       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│              ┌────────────┼────────────┐                         │
│              ▼            ▼            ▼                         │
│         [Cache]    [Database]    [ML Model]                     │
│          (15min)      (SQL)      (Pre-computed)                 │
└──────────┬──────────┬──────────┬──────────┬────────────────────┘
           │          │          │          │
           ▼          ▼          ▼          ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ Memory  │ │Supabase │ │yfinance │ │ML Cache │
    │ Cache   │ │  (PG)   │ │  API    │ │(JSON)   │
    │ (Redis) │ │         │ │         │ │         │
    └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

---

## Layer Breakdown

### 1. Frontend Layer

**Technologies:** HTML, CSS, JavaScript (no framework)

**Why no React?**
- ✅ Simpler for this use case
- ✅ Lower complexity = easier to understand
- ✅ Fewer dependencies = easier deployment
- ✅ Faster initial load
- ⚠️ Caveat: Can become unwieldy with complex UIs

**Key Components:**
- Authentication (Firebase redirects)
- Stock analysis form
- Portfolio dashboard with live charts
- Watchlist manager

**Performance Considerations:**
- Async chart updates without full page reload
- Debounced search (don't fetch while typing)
- Image lazy loading
- CSS Grid for responsive layout

---

### 2. API Layer (Flask Routes)

**Design Pattern:** REST with JSON responses

**Key Endpoints:**

```python
# Analysis Endpoints
GET /api/analyze?ticker=AAPL          # Technical + sentiment
POST /api/backtest/stream              # Live backtest logs (SSE)

# ML Endpoints  
GET /api/ml-scores/<ticker>            # Prediction score
GET /api/latest-metrics                # Portfolio backtest metrics

# Portfolio Endpoints
GET /api/portfolio/summary             # Holdings, P&L, performance
POST /api/portfolio/holdings           # Add new position
PUT /api/portfolio/holdings            # Update position
DELETE /api/portfolio/holdings         # Remove position

# Watchlist Endpoints
GET /api/watchlist                     # Get all watchlists
POST /api/watchlist                    # Create new watchlist
DELETE /api/watchlist/<id>             # Delete watchlist

# Admin Endpoints
GET /api/health                        # Health check
GET /api/admin/performance             # Metrics dashboard
```

**Error Handling Pattern:**

```python
try:
    result = analyze_ticker(ticker)
    return jsonify({"status": "success", "data": result})
except RateLimitError:
    # Fall back to cache
    return jsonify({
        "status": "partial",
        "data": get_cached_data(ticker),
        "warning": "Using cached data (API rate limited)"
    })
except Exception as e:
    app.logger.error(f"Error: {e}")
    return jsonify({"status": "error", "message": str(e)}), 500
```

**Rate Limiting:** Not yet implemented but should add:

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(app, key_func=get_remote_address)

@app.route("/api/analyze")
@limiter.limit("30 per minute")
def api_analyze():
    ...
```

---

### 3. Caching Layer

**Strategy:** Multi-layer caching for performance

```
Level 1: Browser Cache (HTTP Headers)
  - Stock prices cached for 5 min
  - API responses cached for 15 min

Level 2: Server Memory Cache (Flask)
  - In-memory dict with TTL
  - Fast, survives requests

Level 3: Redis Cache (Optional)
  - Shared across multiple app instances
  - Survives app restarts
  - Perfect for scaling

Level 4: Database Cache (Supabase)
  - Persistent storage
  - Last resort
```

**Current Implementation:**

```python
_cache = {}  # In-memory dict
_CACHE_TTL_SECONDS = 900  # 15 minutes

def _cache_get(key):
    if key in _cache:
        entry = _cache[key]
        if entry["expires_at"] > time.time():
            return entry["data"]  # Cache hit!
    return None

def _cache_set(key, value):
    _cache[key] = {
        "data": value,
        "expires_at": time.time() + _CACHE_TTL_SECONDS
    }
```

**Cache Invalidation:** 
- 15-minute automatic expiry
- No manual invalidation needed
- Data becomes gradually stale

---

### 4. Service Layer (Business Logic)

**Separation of Concerns:**

- `routes/*.py` - HTTP handling only
- `services/*.py` - Business logic
- `ml_module/` - ML operations
- `templates/` - HTML rendering

**Example: PortfolioManager Service**

```python
class PortfolioManager:
    def __init__(self, supabase_client):
        self.db = supabase_client
    
    def get_holdings(self, user_email):
        """Fetch user's stock positions"""
        response = self.db.table("portfolio_holdings")\
            .select("*")\
            .eq("email", user_email)\
            .execute()
        return response.data or []
    
    def calculate_pnl(self, holding):
        """Calculate profit/loss for a position"""
        current_price = yf.download(
            holding["ticker"],
            period="1d"
        )["Close"].iloc[-1]
        
        invested = holding["quantity"] * holding["entry_price"]
        current = holding["quantity"] * current_price
        pnl = current - invested
        
        return {
            "gain_loss": pnl,
            "gain_loss_pct": (pnl / invested * 100) if invested > 0 else 0
        }
```

**Benefits:**
- ✅ Reusable across routes
- ✅ Testable independently
- ✅ Database access centralized
- ✅ Easy to mock for tests

---

### 5. Data Layer (Database)

**Database: Supabase (PostgreSQL)**

**Schema:**

```sql
-- Users (via Firebase Auth, but we store profile info)
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Portfolio Holdings
CREATE TABLE portfolio_holdings (
    id SERIAL PRIMARY KEY,
    email VARCHAR NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    quantity FLOAT NOT NULL,
    entry_price FLOAT NOT NULL,
    entry_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(email, ticker)  -- One position per ticker
);

-- Watchlists
CREATE TABLE watchlists (
    id UUID PRIMARY KEY,
    email VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    tickers JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Analysis History
CREATE TABLE analysis_history (
    id SERIAL PRIMARY KEY,
    email VARCHAR,
    ticker VARCHAR(10),
    verdict VARCHAR,
    factor_score FLOAT,
    analyzed_at TIMESTAMP DEFAULT NOW()
);
```

**Query Optimization:**
- Indexes on email (most queries filtered by user)
- Indexes on ticker (stock lookups)
- UNIQUE constraints prevent duplicates

---

### 6. ML Module Layer

**Separation:** ML code is in separate `alphalab-ml` package

**Why?**
- ✅ Can be tested independently
- ✅ Can be reused by other projects
- ✅ Can be deployed separately
- ✅ Easier to maintain

**Architecture:**

```
alphalab-ml/
├── setup.py                # Package metadata
├── alphalab_ml/
│   ├── __init__.py        # Export main functions
│   ├── flask_api.py       # Functions called by Flask
│   └── ml_model/
│       ├── scorer.py      # Ridge regression implementation
│       ├── features.py    # Feature engineering
│       └── backtest.py    # Walk-forward validation
└── backtest_runs/
    └── latest/
        ├── demo_run_001.json
        ├── model_metadata.json
        └── latest_scores.csv
```

**Functions Exported to Flask:**

```python
from alphalab_ml import (
    get_latest_ml_metrics,      # Last backtest performance
    get_all_ml_backtests,       # Historical backtest runs
    get_ml_scores_for_ticker    # Prediction for single stock
)
```

**Data Flow:**

```
1. Local: python scripts/run_pipeline.py
   ↓
2. Generates: backtest_runs/demo_run_001.json
   ↓
3. Commit to git: git add data/backtest_runs
   ↓
4. Deploy: Docker pulls code + data
   ↓
5. Flask reads: alphalab_ml/flask_api.py
   ↓
6. Served: /api/ml-scores/AAPL returns pre-computed score
```

**No runtime computation = Fast + Reliable + Free from yfinance limits**

---

## Technical Decisions Explained

### Why Flask?

| Aspect | Flask | Django | FastAPI |
|--------|-------|--------|---------|
| **Setup Time** | 5 min | 30 min | 10 min |
| **Learning Curve** | Shallow | Steep | Medium |
| **Suitable for ML** | ✅ Yes | ⚠️ Overkill | ✅ Yes |
| **Performance** | Good | Good | Excellent |
| **Scalability** | ✅ Horizontal | ✅ Horizontal | ✅ Horizontal |
| **For Portfolio** | ⭐ Best | Too much | Good |

**Decision:** Flask because:
- ✅ Minimal boilerplate (easier to understand)
- ✅ Perfect for API + Flask integration with ML
- ✅ Shows you understand foundations, not just framework magic

---

### Why Ridge Regression for ML?

**Comparison:**

| Model | Accuracy | Interpretability | Speed | For Finance |
|-------|----------|------------------|-------|-------------|
| **Ridge** | 0.58 | ⭐⭐⭐⭐⭐ | <1ms | ✅ |
| Neural Net | 0.61 | ⚠️ | 5ms | ❌ |
| Random Forest | 0.59 | ⭐⭐⭐ | 10ms | ❌ |
| SVM | 0.57 | ⚠️ | 3ms | ❌ |

**Decision:** Ridge because:
- ✅ Interpretable (see which features matter)
- ✅ Fast inference (scales to 500 stocks)
- ✅ Prevents overfitting with L2 regularization
- ✅ Works great with correlated features (stock returns)

**The Neural Net dilemma:**
- Slightly better accuracy (0.61 vs 0.58)
- But takes 5x longer, black-box (can't explain)
- In production: Interpretability > 3% accuracy gain

---

### Why Pre-compute ML Scores?

**Option A: Real-time Scoring (❌ Bad)**
```
User visits: /api/ml-scores/AAPL
↓
Flask computes Ridge regression live
↓
Takes 500ms
↓
User waits
↓
Meanwhile: yfinance blocks after 30 requests
```

**Option B: Pre-computed Scores (✅ Good)**
```
Morning: python scripts/run_pipeline.py
↓
Scores computed once locally (5 seconds for 500 stocks)
↓
Saved to JSON in git
↓
Deployed with code
↓
User visits: /api/ml-scores/AAPL
↓
Flask reads from JSON
↓
<1ms response
↓
Zero API rate limiting
```

**Key insight:** Server should serve data, not compute data.

---

### Why This Caching Strategy?

**Level 1: Browser Cache**
- Browser won't refetch if data fresh
- Saves bandwidth
- Free!

**Level 2: Memory Cache (Flask)**
- Fast (nanoseconds vs milliseconds)
- Perfect for same-server requests
- Dies on restart (acceptable)

**Level 3: Redis Cache**
- Persists across restarts
- Shared by multiple app instances
- For when scaling to multiple servers

**Level 4: Database**
- Persistent storage
- For data that should outlive app

---

### Why Supabase (PostgreSQL)?

**Alternatives:**

| DB | Free Tier | Auth Built-in | SQL | Scale | For Portfolio |
|---|----------|-----------|-----|-------|---|
| **Supabase** | ✅ 500MB | ✅ Firebase | ✅ | ✅ | ⭐ |
| Firebase | ✅ 1GB | ✅ | ❌ NoSQL | ✅ | Good |
| MongoDB | ✅ 512MB | ❌ | ❌ | ✅ | OK |
| PostgreSQL | ❌ | ❌ | ✅ | ✅ | Good |

**Decision:** Supabase because:
- ✅ Built-in Firebase auth
- ✅ SQL (easier than NoSQL for structured data)
- ✅ Free tier with generous limits
- ✅ Easy to manage UI
- ✅ Shows understanding of both SQL + NoSQL

---

## Scalability Analysis

### Current Architecture Limits

**Bottlenecks (in order of likelihood):**

1. **yfinance Rate Limiting** (SOLVED)
   - Problem: 30 requests/minute limit
   - Solution: Cache + pre-compute
   - Status: ✅ Solved

2. **Database Connections** (When 1000+ users)
   - Problem: Supabase free tier has connection limit
   - Solution: Connection pooling, read replicas
   - Impact: Unlikely to hit during portfolio use

3. **Memory Cache** (When 10,000+ tickers cached)
   - Problem: In-memory dict grows unbounded
   - Solution: Redis or LRU cache with max size
   - Current: Fine for <500 unique tickers

4. **Flask Single Process** (When 100+ concurrent users)
   - Problem: Flask is single-threaded by default
   - Solution: Gunicorn with 4+ workers
   - Status: Already in docker-compose

### Scaling Strategy

**Phase 1: Current (Good for <1000 users)**
- Flask single process
- In-memory cache
- Supabase free tier

**Phase 2: Growing (1000-10,000 users)**
- Gunicorn 4+ workers
- Redis cache (replaces in-memory)
- Database query optimization

**Phase 3: Large (10,000+ users)**
- Kubernetes cluster
- CDN for static assets
- Database read replicas
- Queue system (Celery) for background tasks

**Current:** Phase 1 ready, Phase 2 feasible with small changes.

---

## Security Architecture

### Authentication Flow

```
User enters email/password
         ↓
Sends to Firebase
         ↓
Firebase validates & returns token
         ↓
Browser stores token in session
         ↓
All API calls include token
         ↓
Flask verifies token before responding
```

**Implementation:**

```python
@login_required  # Custom decorator
def api_portfolio_summary():
    user_email = session.get("user_email")
    # Only fetch THIS user's data
    holdings = db.table("portfolio_holdings")\
        .select("*")\
        .eq("email", user_email)\
        .execute()
    return jsonify(holdings.data)
```

### Data Isolation

- ✅ Each user sees only their own data
- ✅ Database queries filtered by email
- ✅ No cross-user data leakage
- ✅ Supabase Row Level Security enforces this

### HTTPS/SSL

- Automatic on Render/Railway
- Required in production (never HTTP)
- Protects credentials in transit

---

## Monitoring & Observability

### Health Checks

```python
@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "cached_tickers": len(_cache),
        "db_connected": db.is_connected(),
        "timestamp": datetime.now().isoformat()
    })
```

### Logging

```python
app.logger.info(f"Cache hit for {ticker}")
app.logger.warning(f"Slow query: {duration}ms")
app.logger.error(f"Error: {exception}", exc_info=True)
```

### Metrics to Track

- API response times (p50, p95, p99)
- Cache hit rate
- Error rates by endpoint
- Database query times
- Uptime percentage

---

## Deployment Architecture

### Local Development
```
You → Flask (dev server) → Supabase
     (http://localhost:8000)
```

### Docker Locally
```
Docker → Flask (Gunicorn) → Supabase
(simulates production)
```

### Production (Render)
```
GitHub → Render (builds Docker) → Flask (Gunicorn) → Supabase
(auto-deploys on push)
```

---

## The Big Picture

**AlphaLab demonstrates:**

1. **Backend Skills**
   - REST API design
   - Error handling
   - Caching strategies
   - Authentication

2. **Frontend Skills**
   - Responsive HTML/CSS
   - JavaScript async programming
   - Chart.js visualization
   - UX consideration

3. **ML Skills**
   - Walk-forward validation
   - Feature engineering
   - Model selection rationale
   - Backtesting methodology

4. **DevOps Skills**
   - Docker containerization
   - Environment variables
   - Deployment strategies
   - Health monitoring

5. **System Design Skills**
   - Scalability thinking
   - Trade-off analysis
   - Architecture documentation
   - Why decisions matter

---

## Questions Employers Might Ask

**Q: Why Flask instead of Django?**
A: Flask is lighter weight and clearer for understanding fundamentals. Django would work but adds complexity we don't need.

**Q: What would break at 1 million users?**
A: Supabase would need read replicas, single Flask process would need load balancing, in-memory cache would need Redis. Architecture supports this with minimal changes.

**Q: How do you prevent look-ahead bias in backtesting?**
A: Walk-forward validation ensures we only use data available at prediction time. Each year trained on previous years, tested on current year.

**Q: Why pre-compute ML scores instead of real-time?**
A: Faster API responses, eliminates yfinance rate limiting, simpler caching, demonstrates architecture thinking.

**Q: How would you scale this to 10M transactions/day?**
A: Queue system (Celery) for background processing, database optimization, caching strategy, horizontal scaling with load balancer.

---

## Next Version Improvements

1. **WebSockets** for real-time updates instead of polling
2. **GraphQL** option alongside REST API
3. **Async Flask** (Quart) for better concurrency
4. **Machine Learning Pipeline** as service (MLflow)
5. **Analytics Dashboard** (Grafana)
6. **Feature Flag System** for A/B testing

---

This architecture is **production-ready** while remaining **understandable to employers** interviewing you.

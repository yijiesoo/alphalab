# AlphaLab

A stock analysis and portfolio tracking app built with Flask, yfinance, and a local Python analysis engine.

> For learning and research only. Not financial advice.

---

## What it does

- Analyze any ticker with a factor score based on momentum and RSI
- Layer in macro context (VIX, 10Y yield, sector trend)
- Pull and score recent news sentiment using FinBERT or keyword fallback
- Track portfolio holdings with entry price and P&L
- Manage watchlists
- View price charts and signal history
- Run backtests against the local factor-lab pipeline

---

## Tech stack

| Layer | Tools |
|---|---|
| Backend | Python 3.13, Flask 3.1.3 |
| Data | yfinance, pandas, numpy, scipy |
| ML | scikit-learn, xgboost |
| NLP (optional) | transformers, torch, ProsusAI/finbert |
| Auth / DB | Firebase, Supabase |
| News | NewsAPI |
| Dev | pytest, ruff, pylint, Docker |

---

## Project structure

```
alphalab/
├── flask_app/
│   ├── app.py           # Main Flask server and API routes
│   ├── config.py        # Environment config
│   ├── routes/          # Auth and dashboard blueprints
│   ├── services/        # Service layer
│   ├── static/          # Frontend assets
│   └── templates/       # Server-rendered HTML
├── factor-lab/
│   └── src/
│       ├── scorer.py        # Per-ticker analysis and scoring
│       ├── sentiment.py     # News fetching and sentiment classification
│       ├── beginner_guide.py # Plain-English signal explanations
│       ├── macro.py         # VIX, yield, sector context
│       ├── factor_delay.py  # Signal timing analysis
│       ├── backtest.py      # Backtest execution
│       └── ...
├── tests/
├── requirements.txt
└── docker-compose.yml
```

---

## Local setup

```bash
git clone https://github.com/yijiesoo/alphalab.git
cd alphalab

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# fill in your keys (see below)

python flask_app/app.py
```

App runs at `http://127.0.0.1:8000`

---

## Environment variables

```bash
FIREBASE_WEB_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=       # mapped to SUPABASE_KEY in config.py
NEWSAPI_KEY=             # omit to disable news sentiment
FLASK_SECRET_KEY=
```

---

## Optional: FinBERT sentiment

By default, sentiment uses keyword matching. For better financial NLP:

```bash
pip install transformers torch
```

The model downloads on first use. Tradeoff: slower startup, higher memory, meaningfully better sentiment classification.

---

## Docker

A `Dockerfile` and `docker-compose.yml` are included. Two caveats:

- `docker-compose.yml` mounts `../alphalab-ml` which is an external optional package — remove that volume if you don't have it
- The compose file includes Redis, but the current cache is in-process memory, so Redis is not required

For local development, running with plain Python is simpler and more reliable.

---

## API reference

### Core
```
GET  /api/health
GET  /api/analyze?ticker=NVDA
GET  /api/cache
```

### Analysis detail
```
GET  /api/beginner-guide/<ticker>
GET  /api/price-chart?ticker=AAPL&timeframe=6M
GET  /api/signal-history?ticker=AAPL&timeframe=6M
```

### Portfolio
```
GET    /api/portfolio/summary
GET    /api/portfolio/holdings
POST   /api/portfolio/holdings
PUT    /api/portfolio/holdings
DELETE /api/portfolio/holdings
```

### Watchlists
```
GET    /api/watchlists
POST   /api/watchlists
DELETE /api/watchlists/<watchlist_id>
```

### Backtest
```
POST /run
GET  /status
GET  /images
GET  /api/backtest/stream?ticker=NVDA
```

### Optional ML metrics (requires external `alphalab_ml`)
```
GET  /api/latest-metrics
GET  /api/ml-scores/<ticker>
GET  /api/top-ml-picks?limit=10
```

These routes return a fallback error payload if `alphalab_ml` is not installed — they will not crash the app.

---

## Testing

```bash
pytest
pytest tests/test_app.py -v
pytest --cov=. --cov-report=html
```

---

## Known limitations

- **Sentiment schema mismatch:** `beginner_guide.py` expects a numeric sentiment score that `sentiment.py` does not currently return. This is on the fix list.
- **Sentiment is a support signal, not a validated alpha factor.** It enriches the analysis page and helps explain the signal, but has not been backtested against forward returns.
- **Scoring weights are heuristic.** The final verdict in `scorer.py` uses a point system that works for v1 but is not formally validated or tunable.
- **yfinance and NewsAPI** introduce rate limits, latency, and occasional data gaps.
- **Backtest outputs** are educational — not institutional-grade research.

---

## Roadmap

- [ ] Fix sentiment schema mismatch — return numeric score + confidence from `sentiment.py`
- [ ] Backtest sentiment against next-day and next-week returns
- [ ] Make final scoring weights explicit and testable
- [ ] Add AI explanation layer — plain-English summary grounded in existing analysis output
- [ ] Align Docker setup with actual dependencies

---

## License

MIT

## Author

Yijie Soo — [@yijiesoo](https://github.com/yijiesoo)

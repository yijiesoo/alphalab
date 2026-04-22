# AlphaLab: Professional Flask-Based Stock Analysis Platform

AlphaLab is a robust, production-ready Flask web application for advanced stock analysis, portfolio management, and machine learning-powered insights. Designed for both individual investors and professionals, AlphaLab delivers a seamless, modern user experience with a comprehensive suite of features.

## Features

- **Secure User Authentication**: Modern login system with session management and Supabase integration.
- **Stock Analysis API**: Analyze any US equity ticker with factor-based scoring, macro context, and sentiment analysis.
- **ML-Driven Insights**: Access the latest machine learning metrics, backtests, and top stock picks, powered by the `alphalab_ml` module.
- **Portfolio Management**: Track holdings, entry prices, quantities, and real-time P&L with accurate calculations and visualizations.
- **Watchlists**: Create, update, and manage multiple watchlists for different strategies or portfolios.
- **Backtesting Engine**: Run and monitor backtests in the background, with real-time log streaming and output image management.
- **Beginner-Friendly Explanations**: Get clear, accessible explanations of signals and analysis for any ticker.
- **Comprehensive API**: RESTful endpoints for all major features, including analysis history, feedback, and portfolio summaries.
- **Modern UI/UX**: Designed for clarity, speed, and ease of use, with robust error handling and user feedback.

## Technology Stack

- **Backend**: Python 3, Flask, Supabase, yfinance, pandas, dotenv
- **Machine Learning**: Integrates with custom `alphalab_ml` module for advanced analytics
- **Testing**: Full test suite with pytest for reliability and maintainability
- **Deployment**: Ready for production with environment variable support and secure configuration

## Quick Start

1. **Clone the repository:**
	```bash
	git clone https://github.com/yijiesoo/alphalab.git
	cd alphalab
	```
2. **Install dependencies:**
	```bash
	pip install -r requirements.txt
	```
3. **Set up environment variables:**
	- Copy `.env.example` to `.env` and fill in your configuration (Supabase, Gmail, etc.)
4. **Run the Flask app:**
	```bash
	cd flask_app
	python app.py
	```
5. **Access the app:**
	- Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

## Testing

Run the full test suite to ensure everything works as expected:
```bash
PYTHONPATH=. pytest tests/
```

## Folder Structure

- `flask_app/` — Main Flask application (routes, services, config)
- `factor-lab/` — Quantitative research modules and scripts
- `tests/` — Automated test suite

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for improvements or new features.

## License

This project is licensed under the MIT License.

---

**AlphaLab** — Professional-grade stock analysis, made simple.

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
## Badges 
![CI/CD](https://github.com/yijiesoo/alphalab/actions/workflows/ci-cd.yml/badge.svg)

## License

MIT

## Author

Yijie Soo — [@yijiesoo](https://github.com/yijiesoo)

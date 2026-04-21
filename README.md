# AlphaLab

Educational stock analysis and portfolio-tracking app built with Flask, a lightweight HTML/CSS/JS frontend, and a local Python analysis engine in `factor-lab/`.

> This project is for learning and research only. It is **not financial advice**.

---

## What AlphaLab does

AlphaLab combines a few pieces into one app:

- **Single-ticker analysis** via `/api/analyze`
- **Technical scoring** using 12-1 momentum and RSI
- **Macro context** such as VIX and 10Y yield
- **News sentiment** using NewsAPI headlines plus optional FinBERT scoring
- **Beginner-friendly explanations** that translate signals into plain English
- **Portfolio tracking** with holdings, entry price, P&L, and watchlists
- **Backtest execution** for the local factor-lab pipeline
- **Optional ML metrics endpoints** if an external `alphalab_ml` package is available

The project is strongest as a **learning product**: it shows how to connect market data, heuristic scoring, sentiment, and a web app into one usable workflow.

---

## Current architecture

```text
Browser (HTML / CSS / JS)
        │
        ▼
Flask app (`flask_app/`)
        │
        ├── Calls factor-lab analysis modules (`factor-lab/src/`)
        ├── Reads market data from yfinance
        ├── Fetches headlines from NewsAPI
        ├── Stores user data in Supabase
        └── Optionally exposes ML metrics from external `alphalab_ml`
```

### Main code areas

- `flask_app/app.py`  
  Main Flask server, API routes, caching, portfolio/watchlist endpoints

- `flask_app/routes/`  
  Auth and dashboard blueprints

- `flask_app/templates/` and `flask_app/static/`  
  Server-rendered frontend and client-side assets

- `factor-lab/src/scorer.py`  
  Main per-ticker analysis logic

- `factor-lab/src/sentiment.py`  
  News fetching and sentiment classification

- `factor-lab/src/beginner_guide.py`  
  Beginner-facing explanations, confidence, warnings, portfolio suggestions

---

## Features that exist today

### Analysis
- `GET /api/analyze?ticker=NVDA`
- 15-minute server-side analysis cache
- Returns:
  - ticker and company
  - latest price
  - factor score
  - macro context
  - sentiment summary
  - entry/exit watch zones
  - correlation context
  - overall verdict

### News sentiment
- Pulls recent headlines from NewsAPI
- Tries several search queries per ticker/company
- Scores headlines with:
  - **FinBERT** if `transformers` and `torch` are installed
  - **Keyword matching fallback** otherwise
- Caches sentiment results for 4 hours

### Portfolio and watchlists
- Holdings CRUD
- Portfolio summary with current value and gain/loss
- Watchlist CRUD
- Watchlist-level performance endpoint

### Charts and history
- Price chart endpoint
- Signal history endpoint
- Background backtest execution and log streaming

### Beginner UX
- Beginner guide endpoint that explains signals in plain English
- Confidence and warning generation
- Risk/reward helper logic

### Optional ML metrics integration
If `alphalab_ml` is importable, the app also exposes:

- `GET /api/latest-metrics`
- `GET /api/all-backtests`
- `GET /api/ml-scores/<ticker>`

If that package is not present, those routes return fallback error payloads instead of crashing.

---

## Tech stack

### Backend
- Python 3.13
- Flask 3.1.3

### Data / quant
- pandas
- numpy
- scipy
- scikit-learn
- xgboost
- yfinance

### External services
- Supabase
- Firebase
- NewsAPI

### Optional NLP
- transformers
- torch
- ProsusAI/finbert

### Dev / testing
- pytest
- pytest-cov
- ruff
- pylint
- Docker

---

## Sentiment: what it is and what it is not

AlphaLab’s current sentiment pipeline is useful, but it is still **headline sentiment**, not a robust tradable alpha signal.

### What is good about it
- Uses financial-domain FinBERT when available
- Avoids total failure with a keyword fallback
- Caches aggressively to conserve NewsAPI quota
- Gives users contextual qualitative information fast

### Current limitations
- It scores **headlines only**, not full articles
- It does not weight headlines by source quality, recency, or market impact
- It returns mostly **counts + summary text**, not a well-calibrated numeric factor
- In `factor-lab/src/scorer.py`, sentiment only affects verdict with a small heuristic rule
- Some downstream code in `factor-lab/src/beginner_guide.py` appears to expect a numeric sentiment score that `sentiment.py` does not currently return

### Bottom line
The sentiment feature is **good enough as a UX/explainer feature** and **partially useful as a weak signal**, but not yet strong enough to claim that it materially improves price prediction.

---

## My assessment of your news sentiment

Short answer: **decent, but not yet strong**.

What you have now is appropriate for:
- enriching the analysis page
- helping beginners understand “what news flow looks like”
- nudging a verdict when news is clearly one-sided

What it is not yet appropriate for:
- heavy weighting in the final score
- claiming measurable predictive power
- portfolio construction without validation

If you want to say it plainly in product terms:

> The current sentiment is better than decorative text, but still closer to a supporting feature than a core alpha engine.

---

## How to build a stronger bridge between news sentiment and prices

This is the highest-leverage improvement area.

### 1. Return a numeric sentiment factor
Right now you mostly return:

- `positive`
- `negative`
- `neutral`
- `summary`
- `headlines`

Add fields like:

```json
{
  "score": 0.35,
  "score_label": "positive",
  "confidence": 0.72,
  "headline_count": 8
}
```

A practical first formula:

- positive = +1
- neutral = 0
- negative = -1
- sentiment score = average across headlines
- recency weight = newer headlines count more
- confidence = abs(score) adjusted by number of headlines

This fixes the schema mismatch and makes sentiment easier to integrate everywhere else.

### 2. Weight by recency
A headline from 30 minutes ago should matter more than one from 3 days ago.

Simple weighting idea:
- 0-6 hours: weight 1.0
- 6-24 hours: weight 0.7
- 1-3 days: weight 0.4
- older: weight 0.2

### 3. Measure price reaction after news
This is the real bridge.

For each ticker and day:
- collect sentiment score from headlines before market close
- measure next-day return, 3-day return, and 5-day return
- compute:
  - average return after positive news
  - average return after negative news
  - hit rate
  - rank correlation / information coefficient

This tells you whether sentiment predicts anything in your universe.

### 4. Model sentiment-price interaction, not sentiment alone
Pure sentiment is noisy. It gets stronger when combined with trend and regime.

Examples:
- Positive sentiment + strong momentum = continuation candidate
- Positive sentiment + weak price trend = less reliable
- Negative sentiment + overbought RSI = stronger warning
- Strong sentiment in high-VIX regime may behave differently than in calm markets

### 5. Use sentiment as an adjustment, not a replacement
A good product design is:

- factor score stays the base
- sentiment becomes an adjustment layer
- macro is a regime filter

Example:

```text
final_score =
  0.60 * technical_factor_score
+ 0.25 * sentiment_score_scaled
+ 0.15 * macro_regime_score
```

Then test whether this outperforms the baseline.

### 6. Track event categories
Not all news is equal. Earnings, guidance, M&A, regulation, layoffs, product launches, and lawsuits behave differently.

Even a simple rule-based tagger would help:
- earnings
- guidance
- analyst rating
- legal/regulatory
- product/news
- management change

Then test which event types have actual predictive value.

---

## Other ways to improve the app

### Highest priority improvements

#### 1. Fix the sentiment schema mismatch
`beginner_guide.py` expects fields like sentiment score / overall sentiment that are not returned by `sentiment.py`.

This is both a product and code-quality issue.

#### 2. Separate “analysis quality” from “UX explanation”
Right now some logic mixes:
- signal generation
- explanation text
- beginner phrasing

You’ll get cleaner evolution if you return:
- raw metrics
- normalized factor outputs
- interpretation/explainer payloads separately

#### 3. Validate which signals actually help
You already have the foundations for analysis and backtesting. Use that to answer:
- Does sentiment improve next-day or next-week returns?
- Does RSI help on top of momentum?
- Which features help in bull vs bear regimes?

This will move the app from “smart-feeling” to “evidence-based”.

#### 4. Improve the final score design
Current verdict logic in `scorer.py` is mostly a heuristic point system. That’s okay for v1, but it is brittle.

Better next step:
- expose a normalized numeric score for each component
- combine them explicitly
- document the weights
- track score changes over time

#### 5. Improve data transparency
This app already includes disclaimers for delayed data and survivorship bias. Keep pushing that.

Good additions:
- “last updated” timestamp per component
- number of headlines used
- whether FinBERT or fallback mode was used
- price data source and staleness
- confidence / coverage indicator

#### 6. Clean up deployment/documentation mismatches
There are a few repo mismatches today:
- `README.md` overstates maturity and architecture cleanliness
- `docker-compose.yml` references `../alphalab-ml`
- `package.json` is not meaningful frontend tooling
- env names in docs can drift from actual `config.py`

The rewritten README below is meant to fix that.

---

## Should you add an AI feature?

Short answer: **yes, but only the right kind**.

Do **not** add AI just to say the app has AI. You already have ML/sentiment. Another vague chatbot won’t add much.

### AI features worth adding

#### 1. AI explanation layer
Best near-term AI feature.

Examples:
- “Explain this stock in plain English”
- “Why is this a hold and not a buy?”
- “Summarize the 5 headlines and tell me what matters”
- “Translate RSI, momentum, and macro into beginner language”

Why it’s good:
- high user value
- low risk to core signal logic
- easy to frame as educational, not predictive

#### 2. AI news synthesis
Use AI to summarize multiple headlines into:
- major themes
- risks
- catalysts
- consensus tone
- what changed vs last week

This is better than just headline sentiment counts.

#### 3. AI portfolio coach
Examples:
- “Your portfolio is too concentrated in tech”
- “These 3 holdings are highly correlated”
- “Your watchlist lacks defensive names”
- “This stock improves diversification / this one duplicates exposure”

This pairs well with your existing beginner-guide and correlation logic.

### AI features to avoid for now
- “AI predicts tomorrow’s price”
- open-ended stock picking bot
- auto-trading
- overconfident recommendation chatbot

Those add risk fast and are hard to validate.

### Recommendation
If you add one AI feature, make it:

> **AI-generated stock explanation and news summary grounded in your existing analysis output**

That fits the product well.

---

## Recommended roadmap

### Phase 1: tighten the current product
- fix sentiment schema mismatch
- add numeric sentiment score
- show sentiment source/method/confidence
- clean up README and docs
- make final-score weights explicit

### Phase 2: validate signal quality
- backtest sentiment vs next-day / next-week returns
- compare baseline technical score vs technical + sentiment
- publish simple evaluation metrics in the app

### Phase 3: add one AI feature
- AI explanation / synthesis layer
- grounded only on your existing data
- clearly framed as educational assistance

---

## Setup

## Requirements
- Python 3.13+
- pip
- NewsAPI key for sentiment
- Supabase project for watchlists / portfolio / history
- Firebase web API key for auth-related flows

Optional:
- Docker / Docker Compose
- `transformers` + `torch` for FinBERT
- external `alphalab_ml` package if you want the ML metric endpoints fully enabled

---

## Local development

```bash
git clone https://github.com/yijiesoo/alphalab.git
cd alphalab

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
```

Fill in `.env` with the variables listed below, then run:

```bash
python flask_app/app.py
```

App URL:

```text
http://127.0.0.1:8000
```

---

## Environment variables

Based on `.env.example` and `flask_app/config.py`:

```bash
FIREBASE_WEB_API_KEY=your_firebase_web_api_key_here
SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here
NEWSAPI_KEY=your_newsapi_key_here
FLASK_SECRET_KEY=your_secret_key_change_in_production
```

### Notes
- `SUPABASE_ANON_KEY` is what `config.py` reads into `SUPABASE_KEY`
- sentiment will return no headlines if `NEWSAPI_KEY` is missing
- FinBERT is optional and not installed by default

---

## Optional FinBERT setup

If you want better financial sentiment classification:

```bash
pip install transformers torch
```

On first use, the model will download and load lazily.

Tradeoffs:
- better than keyword matching
- slower
- larger disk and memory footprint

---

## Docker

There is a Dockerfile and `docker-compose.yml`, but a few caveats matter:

- `docker-compose.yml` includes Redis, though the current Flask cache is in-process memory
- it also mounts `../alphalab-ml`, which is **outside this repo**
- if you do not have that external folder, some ML metric routes will fall back to stub responses

Build/run basics:

```bash
docker-compose up --build
```

If you want the simplest reliable path for development, local Python execution is currently easier than Docker.

---

## API reference

### Health
```bash
GET /api/health
```

### Analyze one ticker
```bash
GET /api/analyze?ticker=NVDA
```

### Cache status
```bash
GET /api/cache
```

### Latest optional ML metrics
```bash
GET /api/latest-metrics
```

### ML score for a ticker
```bash
GET /api/ml-scores/AAPL
```

### Top cached picks
```bash
GET /api/top-ml-picks?limit=10
```

### Price chart
```bash
GET /api/price-chart?ticker=AAPL&timeframe=6M
```

### Signal history
```bash
GET /api/signal-history?ticker=AAPL&timeframe=6M
```

### Beginner guide
```bash
GET /api/beginner-guide/AAPL
```

### Portfolio summary
```bash
GET /api/portfolio/summary
```

### Portfolio holdings
```bash
GET    /api/portfolio/holdings
POST   /api/portfolio/holdings
PUT    /api/portfolio/holdings
DELETE /api/portfolio/holdings
```

### Watchlists
```bash
GET    /api/watchlists
POST   /api/watchlists
DELETE /api/watchlists/<watchlist_id>
```

### Legacy watchlist endpoint
```bash
GET    /api/watchlist
POST   /api/watchlist
DELETE /api/watchlist
```

### Save analysis history
```bash
POST /api/save-analysis
```

### Analysis history
```bash
GET /api/analysis-history?session_id=default
```

### Feedback
```bash
POST /api/feedback
```

### Backtest routes
```bash
POST /run
GET  /status
GET  /images
GET  /outputs/<filename>
GET  /api/backtest/stream?ticker=NVDA
```

---

## Project structure

```text
alphalab/
├── flask_app/
│   ├── app.py
│   ├── config.py
│   ├── routes/
│   ├── services/
│   ├── static/
│   └── templates/
├── factor-lab/
│   ├── scripts/
│   │   └── run_backtest.py
│   ├── src/
│   │   ├── backtest.py
│   │   ├── beginner_guide.py
│   │   ├── data.py
│   │   ├── factor_delay.py
│   │   ├── factors.py
│   │   ├── macro.py
│   │   ├── metrics.py
│   │   ├── plotting.py
│   │   ├── portfolio.py
│   │   ├── scorer.py
│   │   ├── sentiment.py
│   │   ├── signal_history.py
│   │   └── watchlists.py
├── docs/
├── tests/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Testing

```bash
pytest
```

Focused examples:

```bash
pytest tests/test_app.py -v
pytest tests/test_finbert.py -v
pytest tests/test_sentiment_output.py -v
```

Coverage example:

```bash
pytest --cov=. --cov-report=html
```

---

## Known gaps and honest caveats

These are worth stating clearly:

- Sentiment currently behaves more like a support signal than a validated predictive factor
- Some beginner-guide code expects sentiment score fields not currently returned
- The repo references optional/external `alphalab_ml` integration
- Docker setup is not as self-contained as the repo alone may imply
- yfinance and NewsAPI introduce rate-limit / availability / latency constraints
- Historical and backtest outputs should be treated as educational, not institutional-grade research

---

## Suggested next changes

1. Add numeric sentiment output and confidence
2. Validate sentiment against forward returns
3. Make final scoring weights explicit and testable
4. Add an AI explanation / news-summary layer
5. Keep documentation aligned with code as the product evolves

---

## License

MIT

---

## Author

Yiji Soo  
GitHub: [@yijiesoo](https://github.com/yijiesoo)

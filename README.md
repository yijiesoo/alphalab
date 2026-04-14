# 📈 AlphaLab - AI-Powered Stock Analysis & Portfolio Tracking

**AlphaLab** is a Flask-based investment analysis platform that combines technical indicators, sentiment analysis, and portfolio tracking to help investors make data-driven decisions.

> **Educational tool for stock analysis. Not investment advice.**

---

## ✨ Features

### Core Analysis
- **Technical Indicators**: Momentum (50%) + RSI (50%) composite scoring
- **Sentiment Analysis**: FinBERT-powered financial news sentiment
- **Entry/Exit Zones**: AI-calculated buy/sell price recommendations
- **Market Correlation**: Cross-stock correlation analysis
- **Macro Analysis**: VIX, market trends, volatility metrics

### Portfolio Management
- **Real-time Tracking**: Monitor portfolio P&L, holdings, performance
- **Multi-watchlist Support**: Organize stocks by strategy
- **Performance Metrics**: Sharpe ratio, drawdown, win rate calculations
- **Portfolio Dashboard**: See all holdings at a glance with real-time data

### User Experience
- **Firebase Authentication**: Secure login with email/password
- **Responsive Design**: Works on desktop and mobile
- **Real-time Updates**: Live stock prices and analysis
- **Email Feedback**: Send feedback directly to developers

---

## 🚀 Tech Stack

### Backend
- **Framework**: Flask 3.1.3
- **Database**: Supabase PostgreSQL
- **Auth**: Firebase
- **Stock Data**: yfinance (real-time)
- **News**: NewsAPI (financial sentiment)
- **Sentiment AI**: FinBERT (accuracy: 80%+)
- **Data Processing**: Pandas, NumPy, Scikit-learn

### Frontend
- **Visualization**: Chart.js
- **Templating**: Jinja2
- **Styling**: Bootstrap-based CSS Grid
- **Responsiveness**: Mobile-first design

---

## 📋 Installation

### Requirements
- Python 3.13+
- pip or conda

### Setup

```bash
# 1. Clone repository
git clone https://github.com/yourusername/alphalab.git
cd alphalab

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your API keys and credentials

# 5. Run the app
python flask_app/app.py
# Visit http://localhost:8000
```

---

## 🔑 Environment Variables

Create a `.env` file with:

```bash
# Flask
FLASK_SECRET_KEY=your_secret_key

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key

# Firebase
FIREBASE_WEB_API_KEY=your_firebase_key

# APIs
NEWSAPI_KEY=your_newsapi_key

# Email (Gmail)
GMAIL_USER=your_email@gmail.com
GMAIL_PASSWORD=your_app_password
```

---

## 📁 Project Structure

```
alphalab/
├── flask_app/                    # Main Flask application
│   ├── app.py                   # 1200+ line main app (routes, logic)
│   ├── config.py                # Configuration
│   ├── routes/                  # Blueprint routes
│   │   └── dashboard.py         # Dashboard endpoints
│   ├── services/                # Business logic
│   │   └── supabase_service.py  # Database operations
│   ├── templates/               # HTML templates
│   │   ├── home.html            # Dashboard
│   │   ├── index.html           # Analysis page
│   │   ├── login.html           # Authentication
│   │   └── transparency.html    # Methodology
│   └── static/                  # JavaScript, CSS
│
├── factor-lab/                   # Analysis engine
│   ├── src/
│   │   ├── data.py              # Price data fetching
│   │   ├── factors.py           # Factor calculations
│   │   ├── metrics.py           # Performance metrics
│   │   ├── scorer.py            # Composite scoring
│   │   ├── sentiment.py         # Sentiment analysis
│   │   ├── macro.py             # Macro indicators
│   │   ├── signal_history.py    # Historical signals
│   │   ├── beginner_guide.py    # Educational content
│   │   ├── watchlists.py        # Watchlist management
│   │   └── factor_delay.py      # Momentum timing
│   ├── scripts/
│   │   └── run_backtest.py      # Backtesting script
│   └── outputs/                 # Generated charts
│
├── tests/                        # Test suite
│   ├── test_app.py
│   ├── test_finbert.py
│   └── test_sentiment_output.py
│
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
└── README.md                     # This file
```

---

## 🔄 How It Works

### 1. Data Pipeline
```
yfinance → Price data
NewsAPI → Financial news
FinBERT → Sentiment scores
```

### 2. Analysis Engine
```
Technical Indicators:
- Momentum (50 period) → 50% weight
- RSI (14 period) → 50% weight
- Entry/Exit zones calculated from zones

Sentiment:
- FinBERT scores news (-1 to +1)
- Aggregated over 30 days

Composite Score = (Momentum 50% + RSI 50%) + Sentiment factor
```

### 3. Portfolio Tracking
```
Holdings → Supabase
Real-time prices → yfinance
P&L = (Current price - Avg cost) × Quantity
Performance = Sum(P&L) / Investment
```

---

## 📊 Key Metrics

- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest peak-to-trough decline
- **Win Rate**: % of winning trades
- **Information Coefficient**: Signal quality (0-1)

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_app.py -v

# With coverage
pytest tests/ --cov=flask_app --cov-report=html
```

---

## 🚀 Deployment

### Railway (Recommended)
```bash
# Push to GitHub
git push origin main

# Deploy via Railway.app:
# 1. Go to railway.app
# 2. Connect GitHub
# 3. Deploy from main branch
# 4. Add environment variables
```

**Cost:** $5-15/month

### Docker
```bash
# Build image
docker build -t alphalab:latest .

# Run container
docker run -p 8000:8000 --env-file .env alphalab:latest
```

---

## 💡 API Cost Optimization

Out of the box, APIs are optimized for free/cheap tiers:

```
NewsAPI: 100 calls/day (free tier)
yfinance: Unlimited (free)
FinBERT: Local (no API calls)

With caching:
- Sentiment cached 4 hours (80% fewer calls)
- Batch requests (10 stocks = 1 API call)
- Total cost: $0-15/month ✅
```

---

## ⚠️ Disclaimer

**AlphaLab is an educational tool for learning stock analysis.**

- Not financial advice
- Past performance ≠ future results
- Use at your own risk
- Test thoroughly before real trading

---

## 📞 Support

- **Issues**: GitHub Issues
- **Email**: Support contact
- **Docs**: See code comments and docstrings

---

## 📄 License

MIT License - See LICENSE file

---

## 👨‍💻 Contributing

1. Fork the repo
2. Create feature branch
3. Make changes
4. Submit PR

---

**Last Updated:** April 14, 2026  
**Status:** Production Ready ✅  
**Python:** 3.13+  
**Version:** 2.0 (Feature Complete)

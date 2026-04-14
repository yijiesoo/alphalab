# 📈 AlphaLab - AI-Powered Stock Analysis & Portfolio Tracking

**AlphaLab** is a Flask-based investment analysis platform combining technical analysis, sentiment analysis, and portfolio tracking.

> Educational tool for stock analysis. Not investment advice.

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- PostgreSQL (via Supabase)
- Firebase account

### Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Add environment variables
# Edit .env with your credentials

# Run locally
python -m flask_app.app
```

Visit: `http://localhost:5000`

## 📦 Stack

- **Backend**: Flask 3.1.3, Gunicorn 23.0.0
- **Database**: Supabase (PostgreSQL)
- **Auth**: Firebase
- **Data**: yfinance, Pandas, NumPy
- **Caching**: Redis 5.0.1
- **Sentiment**: FinBERT

## 🌐 Production

Deployed on Railway: `https://alphalab-production-9c91.up.railway.app`

Deploy: `git push origin main`

## 📝 License

Educational use only.

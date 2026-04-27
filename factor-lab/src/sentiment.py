"""
sentiment.py — Fetch news and score sentiment for a stock ticker.

SENTIMENT ANALYSIS OPTIONS:
===========================

1. KEYWORD MATCHING (Default, No Dependencies)
   - Fast, lightweight, no external models
   - Uses simple word lists (POSITIVE_WORDS, NEGATIVE_WORDS)
   - Good for quick analysis, limited accuracy
   - Always available as fallback

2. FinBERT (Financial BERT, Recommended)
   - Deep learning model fine-tuned for financial sentiment
   - Much higher accuracy than keyword matching
   - Understands context and nuance
   - LOCAL model (no rate limits, privacy)
   - Requires: transformers + torch (~1.5GB disk on first use)

   Install FinBERT:
   $ pip install transformers torch

   Cost-Benefit:
   ✅ 80%+ accuracy on financial news
   ✅ No API rate limits
   ✅ Works offline
   ❌ Slower (~500ms per headline on CPU, ~50ms on GPU)
   ❌ Larger memory footprint

USAGE:
======
# Default: Uses FinBERT if available, falls back to keyword matching
result = get_news_sentiment("NVDA", company_name="NVIDIA", use_finbert=True)

# Force keyword matching (ignore FinBERT)
result = get_news_sentiment("NVDA", company_name="NVIDIA", use_finbert=False)

RECOMMENDATION:
================
Use BOTH:
- News API: Provides curated, relevant headlines
- FinBERT: Scores them with high accuracy
This gives you the best of both worlds: relevance + accuracy
"""

import os
import time

import requests

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

# Try to import FinBERT (optional dependency)
try:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    FINBERT_AVAILABLE = True
    print("[sentiment] ✅ FinBERT dependencies available (transformers + torch)")
except ImportError as e:
    FINBERT_AVAILABLE = False
    print(f"[sentiment] ⚠️  FinBERT not available: {e}. Will use keyword matching as fallback.")

# Fallback: Simple keyword-based scorer — no ML dependency, fast, good enough
POSITIVE_WORDS = {
    "beat", "surge", "soar", "record", "growth", "profit", "upgrade",
    "buyback", "dividend", "strong", "outperform", "rally", "gain",
    "raised", "raise", "positive", "exceed", "bullish",
}
NEGATIVE_WORDS = {
    "miss", "fall", "drop", "loss", "layoff", "downgrade", "cut",
    "concern", "risk", "warn", "decline", "weak", "lawsuit", "fine",
    "probe", "bearish", "crash", "plunge", "disappointing",
}

# Global FinBERT model (lazy-loaded on first use)
_finbert_model = None
_finbert_tokenizer = None



def _load_finbert():
    """Load FinBERT model and tokenizer (lazy loading)."""
    global _finbert_model, _finbert_tokenizer
    if _finbert_model is None and FINBERT_AVAILABLE:
        try:
            print("[sentiment] Loading FinBERT model...")
            model_name = "ProsusAI/finbert"
            _finbert_tokenizer = AutoTokenizer.from_pretrained(model_name)
            _finbert_model = AutoModelForSequenceClassification.from_pretrained(model_name)
            print("[sentiment] FinBERT model loaded successfully")
        except Exception as e:
            print(f"[sentiment] Failed to load FinBERT: {e}. Falling back to keyword matching.")
            _finbert_model = None
    return _finbert_model, _finbert_tokenizer


def _score_headline_finbert(headline: str) -> str:
    """Score headline using FinBERT model."""
    model, tokenizer = _load_finbert()

    if model is None:
        # Fallback to keyword matching
        return _score_headline_keyword(headline)

    try:
        inputs = tokenizer(headline, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            outputs = model(**inputs)

        logits = outputs.logits
        probabilities = torch.softmax(logits, dim=1)[0]

        # FinBERT labels: 0=negative, 1=neutral, 2=positive
        sentiment_idx = torch.argmax(probabilities).item()
        sentiment_map = {0: "negative", 1: "neutral", 2: "positive"}

        return sentiment_map.get(sentiment_idx, "neutral")
    except Exception as e:
        print(f"[sentiment] FinBERT error: {e}. Falling back to keyword matching.")
        return _score_headline_keyword(headline)


def _score_headline_keyword(headline: str) -> str:
    """Score headline using keyword matching (fallback)."""
    words = set(headline.lower().split())
    pos_hits = words & POSITIVE_WORDS
    neg_hits = words & NEGATIVE_WORDS
    if pos_hits and not neg_hits:
        return "positive"
    elif neg_hits and not pos_hits:
        return "negative"
    else:
        return "neutral"


# ---------------------------------------------------------------------------
# Sentiment result cache: keyed by ticker (or company query), TTL = 4 hours.
# This dramatically reduces NewsAPI usage on the free tier (100 calls/day).
# ---------------------------------------------------------------------------
_sentiment_result_cache: dict = {}
_SENTIMENT_CACHE_TTL = 4 * 60 * 60  # 4 hours in seconds


def _build_sentiment_result(
    pos: int,
    neg: int,
    neu: int,
    headlines: list,
    method: str,
) -> dict:
    """
    Build a backward-compatible sentiment payload.

    Existing consumers use count fields (`positive`, `negative`, `neutral`,
    `summary`, `headlines`). Beginner-facing code also expects score-style
    fields such as `score` and `overall_sentiment`.
    """
    total = pos + neg + neu

    if total == 0:
        score = 0.0
        confidence = 0.0
    else:
        # Average headline polarity on a -1..1 scale
        score = (pos - neg) / total

        # Confidence increases when sentiment is both directional and supported
        # by more headlines, capped once we have a modest sample size.
        coverage_factor = min(total / 5, 1.0)
        confidence = abs(score) * coverage_factor

    if score > 0.15:
        sentiment_label = "positive"
    elif score < -0.15:
        sentiment_label = "negative"
    else:
        sentiment_label = "neutral"

    return {
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "summary": _plain_summary(pos, neg, neu, total),
        "headlines": headlines[:5],  # cap at 5 for display
        "score": round(score, 2),
        "overall_sentiment": round(score, 2),
        "confidence": round(confidence, 2),
        "method": method,
        "sentiment_label": sentiment_label,
        "headline_count": total,
    }


def get_news_sentiment(ticker: str, company_name: str = None, use_finbert: bool = True) -> dict:
    """
    Fetches recent headlines for a ticker and scores sentiment.
    Results are cached per-ticker for 4 hours to conserve NewsAPI quota
    (free tier: 100 requests/day; each analysis makes up to 4 calls).

    Parameters
    ----------
    ticker : str
        Stock ticker symbol
    company_name : str, optional
        Company name for better search results
    use_finbert : bool, default True
        If True, use FinBERT for sentiment scoring (requires transformers + torch).
        If False or FinBERT unavailable, falls back to keyword matching.
    """
    now = time.time()
    cache_key = ticker.upper()

    # Return cached result if still fresh
    if cache_key in _sentiment_result_cache:
        cached = _sentiment_result_cache[cache_key]
        if cached["expires_at"] > now:
            print(f"[sentiment] Cache hit for {cache_key} (TTL {int(cached['expires_at'] - now)}s remaining)")
            return cached["data"]

    query = company_name if company_name else ticker
    headlines = _fetch_headlines(query)
    print(f"[sentiment] Fetched {len(headlines)} headlines for {query}")

    if not headlines:
        print(f"[sentiment] No headlines found for {query}")
        result = _build_sentiment_result(
            pos=0,
            neg=0,
            neu=0,
            headlines=[],
            method="no_news",
        )
        result["summary"] = "No recent news found."
        _sentiment_result_cache[cache_key] = {"data": result, "expires_at": now + _SENTIMENT_CACHE_TTL}
        return result

    # Choose scoring method
    if use_finbert and FINBERT_AVAILABLE:
        print(f"[sentiment] Using FinBERT to score {len(headlines)} headlines")
        score_fn = _score_headline_finbert
        method = "finbert"
    else:
        print(f"[sentiment] Using keyword matching to score {len(headlines)} headlines")
        score_fn = _score_headline_keyword
        method = "keyword"

    scored = [score_fn(h) for h in headlines]
    pos = sum(1 for s in scored if s == "positive")
    neg = sum(1 for s in scored if s == "negative")
    neu = sum(1 for s in scored if s == "neutral")

    result = _build_sentiment_result(
        pos=pos,
        neg=neg,
        neu=neu,
        headlines=headlines,
        method=method,
    )
    _sentiment_result_cache[cache_key] = {"data": result, "expires_at": now + _SENTIMENT_CACHE_TTL}
    return result


def _fetch_headlines(query: str) -> list:
    if not NEWSAPI_KEY:
        print("[sentiment] NEWSAPI_KEY not set, cannot fetch headlines")
        return []
    try:
        url = "https://newsapi.org/v2/everything"

        # Try multiple search queries for better results
        search_queries = [
            f'"{query}" stock',  # Exact phrase with "stock"
            f"{query} earnings",  # Earnings-related news
            f"{query} trading",   # Trading news
            query,                # Just the ticker/company name
        ]

        all_articles = []
        seen_titles = set()

        for search_query in search_queries:
            print(f"[sentiment] Querying News API: {search_query}")
            params = {
                "q": search_query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 5,
                "apiKey": NEWSAPI_KEY,
            }
            r = requests.get(url, params=params, timeout=5)
            articles = r.json().get("articles", [])
            print(f"[sentiment] Found {len(articles)} articles for query '{search_query}'")

            for a in articles:
                title = a.get("title", "")
                if title and title not in seen_titles:
                    all_articles.append(title)
                    seen_titles.add(title)
                    if len(all_articles) >= 10:
                        return all_articles

        print(f"[sentiment] Total {len(all_articles)} unique headlines fetched")
        return all_articles[:10]
    except Exception as e:
        print(f"[sentiment] Error fetching headlines: {e}")
        return []


def _plain_summary(pos: int, neg: int, neu: int, total: int) -> str:
    if total == 0:
        return "No headlines found."
    if pos > neg * 2:
        tone = "mostly positive"
    elif neg > pos * 2:
        tone = "mostly negative"
    elif pos > neg:
        tone = "slightly positive"
    elif neg > pos:
        tone = "slightly negative"
    else:
        tone = "mixed"
    return f"{total} recent headlines — sentiment is {tone} ({pos} positive, {neg} negative, {neu} neutral)."

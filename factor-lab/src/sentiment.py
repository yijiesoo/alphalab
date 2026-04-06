import os
import requests

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

# Simple keyword-based scorer — no ML dependency, fast, good enough
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


def get_news_sentiment(ticker: str, company_name: str = None) -> dict:
    """
    Fetches recent headlines for a ticker and scores sentiment.
    Returns a summary dict with counts and a plain-English line.
    """
    query = company_name if company_name else ticker
    headlines = _fetch_headlines(query)

    if not headlines:
        return {
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "summary": "No recent news found.",
            "headlines": [],
        }

    scored = [_score_headline(h) for h in headlines]
    pos = sum(1 for s in scored if s == "positive")
    neg = sum(1 for s in scored if s == "negative")
    neu = sum(1 for s in scored if s == "neutral")

    return {
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "summary": _plain_summary(pos, neg, neu, len(headlines)),
        "headlines": headlines[:5],  # cap at 5 for display
    }


def _fetch_headlines(query: str) -> list:
    if not NEWSAPI_KEY:
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
            params = {
                "q": search_query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 5,
                "apiKey": NEWSAPI_KEY,
            }
            r = requests.get(url, params=params, timeout=5)
            articles = r.json().get("articles", [])
            
            for a in articles:
                title = a.get("title", "")
                if title and title not in seen_titles:
                    all_articles.append(title)
                    seen_titles.add(title)
                    if len(all_articles) >= 10:
                        return all_articles
        
        return all_articles[:10]
    except Exception:
        return []


def _score_headline(headline: str) -> str:
    words = set(headline.lower().split())
    pos_hits = words & POSITIVE_WORDS
    neg_hits = words & NEGATIVE_WORDS
    if pos_hits and not neg_hits:
        return "positive"
    elif neg_hits and not pos_hits:
        return "negative"
    else:
        return "neutral"


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

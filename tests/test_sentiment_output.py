#!/usr/bin/env python3
"""Test sentiment results from analyze_ticker."""

import sys

sys.path.insert(0, './factor-lab')

from dotenv import load_dotenv

# Load .env first
load_dotenv()

import json  # noqa: E402

from src.scorer import analyze_ticker  # noqa: E402

print("[TEST] Analyzing NVDA with FinBERT sentiment...")
print("=" * 70)

result = analyze_ticker('NVDA')

# Focus on sentiment output
sentiment_data = result.get('sentiment', {})
print("\n📊 SENTIMENT RESULTS:")
print("-" * 70)
print(f"Positive: {sentiment_data.get('positive', 0)}")
print(f"Negative: {sentiment_data.get('negative', 0)}")
print(f"Neutral:  {sentiment_data.get('neutral', 0)}")
print(f"Summary:  {sentiment_data.get('summary', 'N/A')}")
print("\nHeadlines analyzed:")
for i, headline in enumerate(sentiment_data.get('headlines', []), 1):
    print(f"  {i}. {headline}")

print("\n" + "-" * 70)
print("Full sentiment object:")
print(json.dumps(sentiment_data, indent=2, default=str))

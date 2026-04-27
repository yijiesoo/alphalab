#!/usr/bin/env python3
"""Quick test script for FinBERT loading."""

import sys
sys.path.insert(0, './factor-lab')

import os
from dotenv import load_dotenv

# Load .env first
load_dotenv()

print("[TEST] FinBERT Loading Test")
print("=" * 50)

# Import after env is loaded
from src.sentiment import _score_headline_finbert, FINBERT_AVAILABLE

print(f"[DEBUG] FINBERT_AVAILABLE: {FINBERT_AVAILABLE}")

if FINBERT_AVAILABLE:
    print("\n[TEST] Testing FinBERT directly on sample headlines...")
    test_headlines = [
        "NVIDIA beats earnings expectations, stock surges",
        "Apple stock falls as sales miss expectations",
        "Tesla continues expansion with new factory",
    ]
    
    for headline in test_headlines:
        print(f"\n  Headline: {headline}")
        result = _score_headline_finbert(headline)
        print(f"  Sentiment: {result}")
    
    print("\n" + "=" * 50)
    print("[TEST] ✅ FinBERT loaded and working successfully!")
else:
    print("[ERROR] ❌ FinBERT not available!")

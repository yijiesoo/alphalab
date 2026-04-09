#!/usr/bin/env python3
"""
Migration script to add multiple watchlists support.
Creates new watchlists table and migrates existing data.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ SUPABASE_URL or SUPABASE_ANON_KEY not set in .env")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# SQL to create watchlists table
CREATE_WATCHLISTS_TABLE = """
CREATE TABLE IF NOT EXISTS watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT 'My Watchlist',
    tickers TEXT[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(email, name),
    FOREIGN KEY (email) REFERENCES auth.users(email) ON DELETE CASCADE
);

-- Add RLS policies
ALTER TABLE watchlists ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own watchlists" ON watchlists
    FOR SELECT USING (auth.jwt()->>'email' = email);

CREATE POLICY "Users can insert their own watchlists" ON watchlists
    FOR INSERT WITH CHECK (auth.jwt()->>'email' = email);

CREATE POLICY "Users can update their own watchlists" ON watchlists
    FOR UPDATE USING (auth.jwt()->>'email' = email);

CREATE POLICY "Users can delete their own watchlists" ON watchlists
    FOR DELETE USING (auth.jwt()->>'email' = email);

-- Create index for faster lookups
CREATE INDEX idx_watchlists_email ON watchlists(email);
"""

print("🚀 Creating watchlists table...")
try:
    # Execute via SQL
    from supabase import PostgrestAPIResponse
    response = supabase.postgrest.query(CREATE_WATCHLISTS_TABLE)
    print("✅ Watchlists table created successfully!")
except Exception as e:
    print(f"⚠️  Error creating table: {e}")
    print("   This might be OK if table already exists")

# Migrate existing data from old watchlist table
print("\n📊 Migrating existing watchlists...")
try:
    old_watchlists = supabase.table("watchlist").select("email, tickers").execute()
    
    for record in old_watchlists.data:
        email = record.get("email")
        tickers = record.get("tickers", [])
        
        if email and tickers:
            print(f"  Migrating {len(tickers)} stocks for {email}...")
            try:
                supabase.table("watchlists").insert({
                    "email": email,
                    "name": "My Watchlist",  # Default name
                    "tickers": tickers
                }).execute()
                print(f"  ✅ Migrated {email}")
            except Exception as e:
                print(f"  ⚠️  Could not migrate {email}: {e}")
    
    print("\n✅ Migration complete!")
except Exception as e:
    print(f"❌ Migration error: {e}")

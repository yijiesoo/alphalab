# Developer Setup Guide - Firebase & Supabase Configuration

This guide helps developers set up the alphalab app locally with Firebase authentication and Supabase database.

## Problem
When cloning the repo, you get "Firebase not configured" error because `.env` file is **not included** in git for security reasons.

## Solution: Create Your Own `.env` File

### Step 1: Clone the Repository
```bash
git clone https://github.com/yijiesoo/alphalab.git
cd alphalab
```

### Step 2: Create `.env` File
Create a new file called `.env` in the project root:

```bash
# macOS/Linux
touch .env

# Windows (PowerShell)
New-Item -Path ".env" -ItemType File
```

### Step 3: Get Credentials from the Original Developer
Ask the developer (or team lead) for these values:

1. **Firebase Web API Key** (`FIREBASE_WEB_API_KEY`)
   - From Firebase Console → Project Settings → Web API Key
   
2. **Supabase URL** (`SUPABASE_URL`)
   - From Supabase Dashboard → Project URL
   
3. **Supabase Anon Key** (`SUPABASE_ANON_KEY`)
   - From Supabase Dashboard → Project → API → anon (public) key
   
4. **News API Key** (`NEWSAPI_KEY`) - Optional
   - From https://newsapi.org/dashboard (optional for sentiment analysis)
   
5. **Flask Secret Key** (`FLASK_SECRET_KEY`)
   - Ask developer or generate: `python3 -c "import secrets; print(secrets.token_hex(32))"`

### Step 4: Populate Your `.env` File
Copy these credentials into your `.env` file:

```bash
# Firebase Configuration
FIREBASE_WEB_API_KEY=your_actual_firebase_key_here

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key_here

# News API (Optional)
NEWSAPI_KEY=your_newsapi_key_here

# Flask Session Secret (Generate new or ask developer)
FLASK_SECRET_KEY=your_secret_key_here
```

### Step 5: Verify Setup
```bash
# Check that Flask can load with proper config
python3 -c "from flask_app.app import app; print('✅ Firebase configured!')"
```

### Step 6: Run the App
```bash
# Start Flask on localhost:8000
python3 flask_app/app.py
```

Then open http://127.0.0.1:8000 in your browser.

---

## Troubleshooting

### "Firebase not configured"
- **Cause**: `.env` file missing or `FIREBASE_WEB_API_KEY` not set
- **Fix**: Follow steps 2-4 above, ensure `.env` exists with correct values

### "Supabase not initialized"
- **Cause**: `SUPABASE_URL` or `SUPABASE_ANON_KEY` missing
- **Fix**: Verify both keys are in `.env` file

### "Port 8000 already in use"
- **Cause**: Flask server already running
- **Fix**: 
  ```bash
  pkill -f "python3 flask_app" || true
  # Then restart: python3 flask_app/app.py
  ```

### "ModuleNotFoundError: No module named 'src'"
- **Cause**: Not in correct directory when running Flask
- **Fix**: Make sure you're in `/alphalab` root directory, not `flask_app/`

---

## Security Notes

⚠️ **Never commit `.env` file** - It contains sensitive credentials
- `.env` is already in `.gitignore`
- Always use environment variables for secrets
- Share credentials through secure channels (1Password, LastPass, email, etc.), never in chat/Slack

## Questions?
Ask the original developer for help with credentials!

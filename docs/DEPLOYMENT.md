# 🚀 Deployment Guide: AlphaLab

This guide walks you through deploying AlphaLab to Render (free tier), Railway, or AWS.

---

## Option 1: Deploy to Render (RECOMMENDED) ⭐

Render is free, fast, and perfect for portfolio projects.

### Prerequisites

- GitHub account with repo pushed
- Supabase account with database set up
- Firebase project created

### Step 1: Push Code to GitHub

```bash
# Make sure everything is committed
git status

# Push to GitHub
git push origin main
```

### Step 2: Create Render Account

1. Go to https://dashboard.render.com
2. Sign up (use GitHub account for easier integration)
3. Click "Connect GitHub account"

### Step 3: Create Web Service

1. Click "New +" button
2. Select "Web Service"
3. Connect to your `alphalab` repository
4. Fill in details:
   - **Name:** `alphalab`
   - **Environment:** `Python 3`
   - **Region:** Choose closest to you (or `Oregon` for US)
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python flask_app/app.py`

### Step 4: Add Environment Variables

In Render dashboard, go to **Environment**:

```
FLASK_ENV=production
SECRET_KEY=your-secret-key-change-me

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key

FIREBASE_API_KEY=your-firebase-key
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
FIREBASE_MESSAGING_SENDER_ID=your-id
FIREBASE_APP_ID=your-app-id
FIREBASE_WEB_API_KEY=your-web-key

GMAIL_USER=your-email@gmail.com
GMAIL_PASSWORD=your-app-password

NEWSAPI_KEY=your-newsapi-key
```

### Step 5: Deploy!

1. Click "Deploy"
2. Watch the build logs
3. Once green checkmark appears, your app is live!

### Access Your App

Your app will be at: `https://alphalab.onrender.com`

(Render assigns a random subdomain; you can set a custom domain in settings)

### Important Notes

**Free Tier Limitations:**
- ⏸️ App goes to sleep after 15 min of inactivity
- 🔄 Wakes up when someone visits (takes ~30 seconds)
- 💰 Upgrade to paid ($7/month) for always-on

**For Portfolio Projects:**
- Sleep mode is fine! Shows you understand deployment
- Interviewers will see the cold-start delay, won't mind
- Actually shows good cost optimization thinking!

---

## Option 2: Deploy to Railway.app

Railway has better performance than Render and $5/month free credits.

### Step 1: Create Railway Account

1. Go to https://railway.app
2. Sign up with GitHub
3. Allow GitHub integration

### Step 2: Create New Project

1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose `alphalab` repository
4. Click "Deploy Now"

### Step 3: Add Environment Variables

1. Go to project settings
2. Add variables:

```
FLASK_ENV=production
SECRET_KEY=your-secret-key
SUPABASE_URL=...
# ... rest of your .env variables
```

### Step 4: Done!

Railway auto-detects Flask and deploys. Your app is live!

URL format: `https://alphalab-production.up.railway.app`

### Cost

- $5/month free credits (usually enough)
- After that: $0.50/hour for always-on service
- Very affordable!

---

## Option 3: Deploy to AWS Free Tier (EC2 Micro)

AWS gives 1 year free, great for learning DevOps.

### Prerequisites

- AWS Account (requires credit card, but free tier)
- Key pair created in EC2

### Step 1: Launch EC2 Instance

1. Go to AWS Console
2. Navigate to EC2 → Instances
3. Click "Launch Instances"
4. Choose:
   - **AMI:** Ubuntu 22.04 LTS (free tier eligible)
   - **Instance type:** t2.micro (free tier eligible)
   - **Storage:** 30 GB (free tier limit)
5. Create security group allowing ports 22 (SSH) and 80 (HTTP)
6. Launch!

### Step 2: SSH into Instance

```bash
chmod 600 your-key.pem
ssh -i your-key.pem ubuntu@your-instance-public-ip
```

### Step 3: Install Dependencies

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Python & pip
sudo apt-get install -y python3-pip python3-venv git

# Install system packages
sudo apt-get install -y build-essential libssl-dev libffi-dev python3-dev

# Clone repo
git clone https://github.com/yijiesoo/alphalab.git
cd alphalab

# Create virtual env
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Set Up Environment Variables

```bash
cp .env.example .env
nano .env  # Edit with your Supabase, Firebase keys
```

### Step 5: Run with Gunicorn (Production Server)

```bash
# Install gunicorn
pip install gunicorn

# Run Flask app
cd flask_app
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### Step 6: Set Up Systemd Service (Auto-restart)

```bash
sudo nano /etc/systemd/system/alphalab.service
```

Add:

```ini
[Unit]
Description=AlphaLab Flask Application
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/alphalab/flask_app
ExecStart=/home/ubuntu/alphalab/venv/bin/gunicorn -w 4 -b 0.0.0.0:8000 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl start alphalab
sudo systemctl enable alphalab  # Auto-start on reboot

# Check status
sudo systemctl status alphalab
```

### Step 7: Set Up Nginx Reverse Proxy

```bash
sudo apt-get install -y nginx

sudo nano /etc/nginx/sites-available/default
```

Edit to:

```nginx
server {
    listen 80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Then:

```bash
sudo nginx -t
sudo systemctl restart nginx
```

### Step 8: Access Your App

Visit your EC2 instance's public IP address:
```
http://your-ec2-public-ip
```

### Cost

- **Year 1:** FREE (t2.micro + 30GB storage included)
- **Year 2+:** ~$10-15/month
- **Learning:** Tons of DevOps experience!

---

## Local Deployment with Docker

Deploy everything locally for testing before going live.

### Prerequisites

- Docker installed
- Docker Compose installed

### Step 1: Create .env File

```bash
cp .env.example .env
# Edit .env with your values
nano .env
```

### Step 2: Run Docker Compose

```bash
docker-compose up -d
```

### Step 3: Check Logs

```bash
docker-compose logs -f web
```

### Step 4: Access App

Visit: `http://localhost:8000`

### Stop Everything

```bash
docker-compose down
```

---

## Troubleshooting

### App Won't Start

**Check logs:**

**Render:** View build logs in dashboard  
**Railway:** Click "Logs" tab  
**AWS:** SSH and run `sudo journalctl -u alphalab -f`

**Common issues:**

```bash
# Missing dependencies
Error: ModuleNotFoundError: No module named 'flask'
→ Make sure requirements.txt is in repo root

# Bad environment variables
Error: SUPABASE_URL is required
→ Check Environment section in dashboard

# Database connection
Error: Failed to connect to Supabase
→ Check SUPABASE_URL and SUPABASE_KEY are correct

# Port already in use
Address already in use: 0.0.0.0:8000
→ Change port in app.py or docker-compose.yml
```

### App Sleeps on Render

Render free tier sleeps after 15 minutes. This is expected!

**To upgrade:**
1. Go to Render dashboard
2. Click your service
3. Click "Settings"
4. Change plan to "Standard" ($7/month)
5. App stays awake 24/7

### Database Connection Slow

**Reduce queries:**
- Add caching (already done with 15-min TTL)
- Use connection pooling
- Optimize database queries

**Check Supabase stats:**
1. Go to Supabase dashboard
2. Check "Database" → "Query Performance"
3. Look for slow queries

### yfinance Gets Rate Limited

**Solution:** Already implemented!

- We cache results for 15 minutes
- Serve cached data if API fails
- If deploying, use pre-computed data

**If still having issues:**
- Use Alpha Vantage API instead
- Or use IEX Cloud
- Pre-compute everything locally

---

## Performance Optimization

### Monitor Performance

**Render:**
1. Click service
2. Go to "Logs"
3. Look for slow requests

**Check response times:**

```bash
curl -w "\nTime: %{time_total}s\n" https://your-app.onrender.com/api/health
```

### Optimize Slow Endpoints

**Profile Flask app:**

```python
# In app.py
from werkzeug.middleware.profiler import ProfilerMiddleware

app = ProfilerMiddleware(app, restrictions=[30])
```

Then check `/profile` endpoint in logs.

### Enable Caching Headers

Already done in app.py:

```python
@app.after_request
def add_cache_headers(response):
    if response.status_code == 200:
        response.cache_control.max_age = 300  # 5 minutes
    return response
```

---

## Monitoring in Production

### Set Up Health Checks

**Render automatically checks:**
```
GET /api/health every 30 seconds
```

**Check manually:**

```bash
curl https://your-app.onrender.com/api/health
```

Response:
```json
{
  "status": "ok",
  "cached_tickers": 5
}
```

### Set Up Error Notifications

**Using Sentry (free tier):**

1. Create Sentry account
2. Install: `pip install sentry-sdk`
3. Add to Flask app:

```python
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="https://your-key@sentry.io/project-id",
    integrations=[FlaskIntegration()]
)
```

Now errors auto-report to Sentry dashboard.

### Monitor Uptime

**Using Uptime Robot (free):**

1. Go to https://uptimerobot.com
2. Create account
3. Add monitor for: `https://your-app.onrender.com/api/health`
4. Get alerts if app goes down

---

## CI/CD: Auto-Deploy on Push

### Set Up GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Render

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to Render
        run: curl ${{ secrets.RENDER_DEPLOY_HOOK }}
```

Then:

1. Get your Render deploy hook URL
2. Add to GitHub secrets: `RENDER_DEPLOY_HOOK`
3. Now every git push auto-deploys!

---

## Rollback in Case of Issues

**Render:**
1. Go to dashboard
2. Click "Deploys"
3. Select previous deployment
4. Click "Rollback"

**Railway:**
1. Click "Deployments"
2. Select previous
3. Right-click → "Revert"

**AWS:**
```bash
# SSH into instance
ssh -i key.pem ubuntu@your-ip

# Stop current version
sudo systemctl stop alphalab

# Pull old commit
cd alphalab && git checkout <commit-hash>

# Start again
sudo systemctl start alphalab
```

---

## Next Steps

✅ **Done:**
- Deploy to free platform
- Set up environment variables
- Health checks working

📊 **Next:**
- Monitor performance
- Set up alerting
- Consider paid tier when scaling
- Optimize slow endpoints
- Add database backups

---

## Questions?

- **Render not deploying?** Check build logs, make sure Python version is 3.13
- **Database connection fails?** Verify SUPABASE_URL and keys are correct
- **App very slow?** Check cache hit rate at `/api/cache`
- **Rate limited by yfinance?** Already handled with caching layer

Good luck! 🚀

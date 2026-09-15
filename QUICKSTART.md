# Quick Start Guide

## 60-Second Setup

```bash
# 1. Navigate to the project directory
cd myfitnesspal-api

# 2. Install dependencies
cd backend && pip install -r requirements.txt && cd ..

# 3. Start the server
./run.sh
```

Open your browser to **http://localhost:8000**

## First Time Using

1. **Log In**: Enter your MyFitnessPal username/email and password
2. **Log Food**: 
   - Type `chicken breast 150` and click Search
   - Select from the alternatives shown
   - Click Add to log
3. **View Totals**: See calories eaten, exercise, and remaining on the dashboard

## Common Commands

```bash
# Start with auto-reload (for development)
cd backend && uvicorn main:app --reload

# Start on a different port
cd backend && uvicorn main:app --port 5000

# Install only production dependencies
pip install -r requirements.txt

# Test the API
curl http://localhost:8000/docs  # Interactive API documentation
```

## How Food Input Works

The app parses natural language food input:

- `lettuce 85` → 85 grams of lettuce
- `chicken 150g` → 150 grams of chicken
- `pizza 2` → 2 of something (defaults to grams)
- `milk 1 cup` → searches for milk, then you select portion size

After typing your food, the app searches MyFitnessPal's database and shows the top 5 matches with complete nutritional info (calories, protein, carbs, fat).

## Calorie Math

**Remaining Calories = Goal - Eaten + Exercise**

Example:
- Goal: 2000 cal
- Eaten: 1500 cal  
- Exercise: 400 cal
- Remaining: 2000 - 1500 + 400 = **900 cal**

The remaining calories increase when you log exercise (which tracks burned calories).

## What This App Does

✅ Log foods from MyFitnessPal's database  
✅ Search food nutrition information  
✅ Track daily calories (eaten + exercise)  
✅ View remaining calories for the day  
✅ Delete logged entries  
✅ Multiple meal categories (breakfast, lunch, dinner, snacks)  

❌ This is NOT a cloud sync - it's a local web interface  
❌ Sessions are in-memory (lost on server restart)  
❌ No user accounts or data persistence  

## Troubleshooting

**"Login failed"**
- Check your username/password at myfitnesspal.com
- Ensure your account is active

**"Module not found"**
- Run `pip install -r requirements.txt` from the backend directory
- Check Python version: `python3 --version` (needs 3.10+)

**App not loading**
- Check if port 8000 is available: `lsof -i :8000`
- Try a different port: `uvicorn main:app --port 8001`

## Next Steps

- Read [SETUP.md](SETUP.md) for detailed configuration
- Check [README.md](README.md) for full feature documentation
- Review API endpoints in FastAPI docs at `/docs`

## Architecture at a Glance

```
User Browser                Backend Server              MyFitnessPal
     ↓                           ↓                            ↓
Login Form ──────────→ FastAPI /api/login ────────→ NextAuth Flow
  (SPA)                    ↓                              ↓
                      Create CurlCffiClient          Get Session Token
                      Store Session UUID
                           ↓
Query Food ──────────→ /api/search ────────────→ Scrape Search Page
                           ↓
                      Return Top 5 Results
                           ↓
Log Food ────────────→ /api/log ──────────────→ Post to /food/add
                           ↓
Today Summary ───────→ /api/today ───────────→ client.get_date()
                           ↓                      + exercise data
                      Format & Return
```

All communication uses your MyFitnessPal session token. No tokens are stored by this app - just the session ID.

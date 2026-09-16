# MyFitnessPal Web App - Offline-First Architecture

## Overview

This is a **two-layer architecture** that separates data acquisition from data display:

```
┌─────────────────────────────────────────────────────────────┐
│                    WEB APPLICATION                          │
│  (No API calls - reads from local databases only)           │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Food Entry  │  │ Food Library │  │  Exercises   │     │
│  │     Diary    │  │   Display    │  │   Display    │     │
│  │              │  │              │  │              │     │
│  │  localhost:  │  │  .food_cache │  │.exercise_    │     │
│  │    8000      │  │    .json     │  │  cache.json  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ reads
                           │
┌─────────────────────────────────────────────────────────────┐
│           LOCAL DATABASES (JSON Files)                      │
│                                                             │
│  .food_cache.json      .exercise_cache.json                │
│  ├─ food name          ├─ exercise ID                      │
│  ├─ calories           ├─ sport name                       │
│  ├─ macros             ├─ duration                         │
│  └─ nutrition          └─ calories                         │
│                                                             │
│  Food Diary (in-memory, could be persisted)               │
│  └─ entries by date/meal                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ writes
                           │
┌─────────────────────────────────────────────────────────────┐
│               CLI SCRIPTS (Data Acquisition)                │
│                                                             │
│  ┌──────────────────────┐    ┌──────────────────────┐     │
│  │ MFP API Integration  │    │ Polar Flow API       │     │
│  ├──────────────────────┤    │ Integration          │     │
│  │ cli_fetch_food_data  │    ├──────────────────────┤     │
│  │ cli_parse_food_data  │    │ cli_fetch_polar_data │     │
│  │ cli_sync_to_mfp      │    │ cli_parse_polar_data │     │
│  └──────────────────────┘    └──────────────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Principles

### 1. **Offline-First Web App**
- Web application has **zero direct API calls** to MyFitnessPal or Polar Flow
- All data comes from **local JSON databases**
- Works completely offline after initial data download
- No rate limiting issues
- No authentication required in web app

### 2. **CLI-Based Data Acquisition**
- All data downloading/scraping handled by CLI scripts
- Can be run manually or via cron jobs
- Separate from web application concerns
- Can be run on a different machine if needed

### 3. **Clear Separation of Concerns**
- **Web Layer**: Display and local management only
- **CLI Layer**: Data acquisition and syncing only
- **Database Layer**: Persistent JSON files

## Workflow

### Daily Workflow

```bash
# Step 1: Download & parse food data
python backend/cli_fetch_food_data.py --since-last-entry
python backend/cli_parse_food_data.py

# Step 2: Download & parse exercise data
python backend/cli_fetch_polar_data.py --since-last-entry
python backend/cli_parse_polar_data.py

# Step 3: Start web app
python -m uvicorn backend.main:app --reload --port 8000

# Step 4: Use web app to add entries
# → Open browser to http://localhost:8000
# → Add food entries to diary
# → View exercises

# Step 5: Sync food entries to MFP (when ready)
python backend/cli_sync_to_mfp.py
```

### Automated (Cron Job) Workflow

```bash
# Every morning at 6 AM: fetch & parse data
0 6 * * * cd /path/to/app && python backend/cli_fetch_food_data.py --since-last-entry && python backend/cli_parse_food_data.py

# Every evening at 8 PM: sync entries to MFP
0 20 * * * cd /path/to/app && python backend/cli_sync_to_mfp.py
```

## Components

### Web Application

**Backend (FastAPI):**
- `main.py` - Simplified API server
- Only reads from: `.food_cache.json`, `.exercise_cache.json`
- Manages local food diary (in-memory)
- NO authentication required
- NO API calls to external services

**Endpoints:**
```
GET    /api/status                        # Data availability
GET    /api/food-instances                # Food library
GET    /api/food-entries?date=YYYY-MM-DD  # Diary for date
POST   /api/food-entries/add               # Add entry
DELETE /api/food-entries/{date}/{meal}/{idx} # Remove entry
GET    /api/exercises?date=YYYY-MM-DD     # Exercises for date
GET    /api/today?date=YYYY-MM-DD         # Daily summary
```

**Frontend (HTML/JS/CSS):**
- Pure client-side app
- No framework dependencies
- Reads from above endpoints
- Manages local food entry UI

### CLI Scripts

**Data Acquisition:**
- `cli_fetch_food_data.py` - Downloads food data from MyFitnessPal API
- `cli_fetch_polar_data.py` - Downloads exercise data from Polar Flow API
- `cli_parse_food_data.py` - Processes raw food data → `.food_cache.json`
- `cli_parse_polar_data.py` - Processes raw exercise data → `.exercise_cache.json`

**Data Syncing:**
- `cli_sync_to_mfp.py` - Syncs local food entries back to MyFitnessPal API

### Local Databases

**`.food_cache.json`**
```json
[
  {
    "name": "Chicken Breast",
    "measurement": {"unit": "g", "value": 100},
    "calories": 165,
    "protein": 31,
    "carbs": 0,
    "fat": 3.6,
    "fiber": 0,
    "sugar": 0,
    "sodium": 74,
    "cholesterol": 85,
    "saturated_fat": 1.3,
    "potassium": 256
  },
  ...
]
```

**`.exercise_cache.json`**
```json
[
  {
    "id": 8419120864,
    "sport_name": "Strength training",
    "duration_minutes": 37,
    "calories": 322,
    "date": "2026-09-11",
    "start_time": "2026-09-11 17:49:06.881",
    "name": "Polar Flow - Strength training",
    "hr_avg": 122
  },
  ...
]
```

## Advantages

✅ **Reliability**
- Web app never depends on external APIs
- Works offline completely
- No network errors breaking the app

✅ **Performance**
- No API latency in web UI
- Instant data loading
- Batch operations more efficient

✅ **Security**
- No API credentials needed in web app
- Credentials only in CLI scripts
- Can run data scripts on isolated machine

✅ **Scalability**
- Multiple web app instances can share same databases
- CLI scripts can run independently
- No database locking issues

✅ **User Experience**
- Instant UI response
- No "loading..." spinners
- No rate limiting from API
- Can add/edit entries offline

## Adding Features

### To Add a New Data Source
1. Create `cli_fetch_*.py` script (download from API)
2. Create `cli_parse_*.py` script (process to JSON)
3. Add new database file to local storage
4. Create web endpoints to read the new database
5. Update frontend to display new data

### To Add a New Web Feature
1. Add GET/POST endpoints in `main.py`
2. Endpoints read from local databases or memory
3. Update frontend JS to call new endpoints
4. Update frontend UI to display results

## Migration from Old Architecture

If you have data in the old in-memory cache:
1. Run `cli_fetch_*` and `cli_parse_*` scripts to download/populate databases
2. Export any important in-memory data to JSON files
3. Start using web app with new architecture
4. Old authentication/session code is no longer needed

## Configuration

### .env.local

```bash
# For fetch scripts (downloading data)
MFP_USERNAME=your@email.com
MFP_PASSWORD=your_password

# For sync script (uploading data)
MFP_SESSION_COOKIE=your_session_token

POLAR_FLOW_USERNAME=username
POLAR_FLOW_USER_ID=12345678
POLAR_FLOW_COOKIE=full_cookie_string
```

### Application Configuration

All configuration is in `.env.local`. The web app reads:
- Logging level (optional)
- Database file paths (if different from defaults)

No other configuration needed for web app.

## Troubleshooting

**Q: "Food Library is empty"**
- A: Run `cli_fetch_food_data.py` and `cli_parse_food_data.py`
- Check that `.food_cache.json` exists in backend/

**Q: "No exercises showing"**
- A: Run `cli_fetch_polar_data.py` and `cli_parse_polar_data.py`
- Check that `.exercise_cache.json` exists in backend/

**Q: "API credentials not found"**
- A: Set in `.env.local` or use `--cookie` flag with CLI scripts

**Q: "Entries not syncing to MFP"**
- A: Run `cli_sync_to_mfp.py --dry-run` to preview
- Check `.env.local` has MFP credentials
- Look for error messages in logs

## Future Enhancements

Possible improvements without breaking architecture:
1. Persist food diary to disk (instead of memory-only)
2. Add SQLite database layer (instead of JSON)
3. Add scheduled sync jobs
4. Add backup/restore functionality
5. Add data export (CSV, Excel)
6. Add multi-user support (separate databases per user)
7. Add data validation/audit trail

All of these can be added while keeping the offline-first design.

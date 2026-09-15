# CLI Polar Flow Data Tools

Two command-line scripts for downloading and parsing exercise data from Polar Flow:

## 1. Fetch Raw Polar Flow Data

Download raw calendar events from Polar Flow API and save to disk.

### Syntax

```bash
python backend/cli_fetch_polar_data.py --cookie <cookie_string> [DATE_RANGE]
```

### Authentication

**Session Cookie (Required)**
```bash
--cookie <full_cookie_string>
```

To get your cookie:
1. Log in to https://flow.polar.com/
2. Open DevTools (F12) → Network tab
3. Make any request (e.g., navigate to Training/Diary)
4. Copy the full `Cookie` header value
5. Should include: `FLOW_SESSION`, `PLAY_SESSION_FLOW`, `CookieConsent`, etc.

### Date Range (choose one)

#### Today Only
```bash
--today
```

#### Last 2 Weeks
```bash
--last-two-weeks
```

#### Last 30 Days
```bash
--last-month
```

#### Custom Range
```bash
--range-start 2026-09-01 --range-end 2026-09-15
```

### Examples

Fetch last 2 weeks of exercises:
```bash
python backend/cli_fetch_polar_data.py \
  --cookie "CookieConsent=...; FLOW_SESSION=...; PLAY_SESSION_FLOW=..." \
  --last-two-weeks
```

Fetch custom date range:
```bash
python backend/cli_fetch_polar_data.py \
  --cookie "your_full_cookie_string" \
  --range-start 2026-09-01 \
  --range-end 2026-09-15
```

Fetch today's exercises:
```bash
python backend/cli_fetch_polar_data.py \
  --cookie "your_full_cookie_string" \
  --today
```

### Output

Raw calendar events are saved to `data/raw_polar_data/` with filename format:
```
polar_calendar_2026-09-01_2026-09-15_20260915_143052.json
```

Contains:
- Metadata (date range, fetch timestamp, event count)
- Raw Polar Flow API response with all activity data

---

## 2. Parse Polar Flow Data

Parse raw calendar events files into the Exercise Diary JSON.

### Syntax

```bash
python backend/cli_parse_polar_data.py [OPTIONS]
```

### Options

#### Parse All Raw Files (default)
```bash
python backend/cli_parse_polar_data.py
```

#### Parse Specific File
```bash
python backend/cli_parse_polar_data.py --file <filename>
```

Example:
```bash
python backend/cli_parse_polar_data.py --file polar_calendar_2026-09-01_2026-09-15_*.json
```

#### Merge with Existing Cache
By default, replaces the entire cache. To keep existing exercises and add new ones:

```bash
python backend/cli_parse_polar_data.py --merge
```

#### Replace Cache (default)
```bash
python backend/cli_parse_polar_data.py --replace
```

### Processing

The parser:
1. Loads all raw calendar JSON files from `data/raw_polar_data/`
2. Extracts calendar events from API response
3. Parses exercise data from each event
4. Deduplicates by exercise ID (keeps first occurrence)
5. Converts duration from milliseconds to minutes
6. Optionally merges with existing cache
7. Saves to `.exercise_cache.json`

### Output

Updated `.exercise_cache.json` with:
- Deduplicated exercises
- Standardized format with duration, calories, date, etc.
- Additional fields: sport_name, hr_avg, distance, training load, etc.

Example exercise record:
```json
{
  "id": 8419120864,
  "sport_name": "Strength training",
  "duration_minutes": 37,
  "calories": 322,
  "date": "2026-09-11",
  "start_time": "2026-09-11 17:49:06.881",
  "name": "Polar Flow - Strength training",
  "hr_avg": 122,
  "distance": null,
  "trainingLoadHtml": "",
  "trainingLoadProHtml": "10000"
}
```

---

## Workflow Example

### Step 1: Fetch fresh data
```bash
python backend/cli_fetch_polar_data.py \
  --cookie "your_full_cookie_string" \
  --last-month
```

Output: `data/raw_polar_data/polar_calendar_2026-08-15_2026-09-15_*.json`

### Step 2: Parse into database (merge with existing)
```bash
python backend/cli_parse_polar_data.py --merge
```

Output: Updated `.exercise_cache.json` with combined exercises

### Result

- Exercise database expanded with last month's activities
- All exercises deduplicated and standardized
- Ready for syncing to MFP as cardio entries

---

## Data Flow

```
Polar Flow Web App
        ↓
[cli_fetch_polar_data.py]
        ↓
data/raw_polar_data/polar_calendar_*.json (raw JSON)
        ↓
[cli_parse_polar_data.py]
        ↓
backend/.exercise_cache.json (deduplicated, standardized)
        ↓
Sync to MyFitnessPal as Cardio Entries
```

---

## Date Format Notes

- **Input**: YYYY-MM-DD format (e.g., 2026-09-15)
- **API**: Converted to D.M.Y format (e.g., 15.9.2026)
- **Output**: Stored as ISO format (2026-09-15)

The scripts handle conversion automatically.

---

## Cookie Expiration

Polar Flow session cookies expire periodically. If you get a 401 error:

1. Log back into https://flow.polar.com/
2. Get a fresh cookie from the DevTools Network tab
3. Update the `--cookie` parameter

---

## Notes

- Raw data files are kept in `data/raw_polar_data/` for reference and re-processing
- Exercises are deduplicated by ID (prevents duplicates from overlapping date ranges)
- Merge mode combines with existing cache (useful for incremental updates)
- Replace mode rebuilds database from scratch (useful for data cleaning)
- All duration data is converted from milliseconds to minutes
- Calories and duration are required (exercises without both are skipped)

---

## Troubleshooting

### Authentication Failed (401)
- Cookie may have expired
- Get a fresh cookie from Polar Flow
- Ensure you copied the entire `Cookie` header (includes multiple cookies)

### No Raw Files Found
- Run `cli_fetch_polar_data.py` first to download data
- Check `data/raw_polar_data/` directory exists

### Missing Events
- Check date range in fetch command
- Polar may not have activities in that period
- Verify cookie is still valid

### Database Not Updating
- Ensure `.exercise_cache.json` has write permissions
- Check `backend/` directory is writable
- Look for errors in parser output

### API Rate Limiting
- If you get 429 errors, wait a few minutes before retrying
- Avoid fetching same date ranges repeatedly

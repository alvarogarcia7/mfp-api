# CLI Food Database Tools

Two command-line scripts for downloading and parsing food data from MyFitnessPal:

## 1. Fetch Raw Food Data

Download raw food data from MyFitnessPal API and save to disk.

### Syntax

```bash
python backend/cli_fetch_food_data.py [AUTH] [DATE_RANGE]
```

### Authentication (choose one)

#### Password Authentication
```bash
--username <email@example.com> --password <password>
```

#### Session Cookie Authentication
```bash
--cookie <session_token>
```
Also prompts for username interactively.

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

Fetch last 2 weeks of data using password:
```bash
python backend/cli_fetch_food_data.py \
  --username user@example.com \
  --password secret \
  --last-two-weeks
```

Fetch custom date range using session cookie:
```bash
python backend/cli_fetch_food_data.py \
  --cookie <token> \
  --range-start 2026-09-01 \
  --range-end 2026-09-15
```

Fetch today's data:
```bash
python backend/cli_fetch_food_data.py \
  --username user@example.com \
  --password secret \
  --today
```

### Output

Raw food data is saved to `data/raw_food_data/` with filename format:
```
food_data_2026-09-01_2026-09-15_20260915_143052.json
```

Contains:
- Metadata (date range, fetch timestamp, food count)
- Raw food entries with all nutrition data

---

## 2. Parse Food Data

Parse raw food data files into the Food Database JSON (.food_cache.json).

### Syntax

```bash
python backend/cli_parse_food_data.py [OPTIONS]
```

### Options

#### Parse All Raw Files (default)
```bash
python backend/cli_parse_food_data.py
```

#### Parse Specific File
```bash
python backend/cli_parse_food_data.py --file <filename>
```

Example:
```bash
python backend/cli_parse_food_data.py --file food_data_2026-09-01_2026-09-15_20260915_143052.json
```

#### Merge with Existing Cache
By default, replaces the entire cache. To keep existing foods and add new ones:

```bash
python backend/cli_parse_food_data.py --merge
```

#### Replace Cache (default)
```bash
python backend/cli_parse_food_data.py --replace
```

### Processing

The parser:
1. Loads all raw food JSON files from `data/raw_food_data/`
2. Deduplicates by food name (keeps first occurrence)
3. Converts to standard food schema format
4. Validates each food against food_schema.json
5. Optionally merges with existing cache
6. Saves to `.food_cache.json`

### Output

Updated `.food_cache.json` with:
- Deduplicated foods
- Validated against schema
- Standardized format with measurement, nutrition, etc.

---

## Workflow Example

### Step 1: Fetch fresh data
```bash
python backend/cli_fetch_food_data.py \
  --username user@example.com \
  --password secret \
  --last-month
```

Output: `data/raw_food_data/food_data_2026-08-15_2026-09-15_*.json`

### Step 2: Parse into database (merge with existing)
```bash
python backend/cli_parse_food_data.py --merge
```

Output: Updated `.food_cache.json` with combined foods

### Result

- Food database expanded with new foods from last month
- Existing foods preserved
- All foods validated and standardized
- Ready to use in the app

---

## Data Flow

```
MyFitnessPal API
        ↓
[cli_fetch_food_data.py]
        ↓
data/raw_food_data/food_data_*.json (raw JSON)
        ↓
[cli_parse_food_data.py]
        ↓
backend/.food_cache.json (standardized, validated)
        ↓
Web App Food Library
```

---

## Notes

- Raw data files are kept in `data/raw_food_data/` for reference and re-processing
- Parser validates all foods against `food_schema.json`
- Invalid foods are logged but don't stop processing
- Deduplication uses food name as key (case-sensitive)
- Measurement defaults to 100g for all foods
- All nutrition data is converted to float (0.0 if missing)

---

## Troubleshooting

### Authentication Failed
- Check username/password
- For cookies, ensure you copied the full session token
- Token may have expired; fetch a new one

### No Raw Files Found
- Run `cli_fetch_food_data.py` first to download data
- Check `data/raw_food_data/` directory exists

### Validation Errors
- Check that foods match `food_schema.json` structure
- Look for missing required fields
- Invalid foods are skipped (see logs)

### Database Not Updating
- Ensure `.food_cache.json` has write permissions
- Check `backend/` directory is writable
- Look for errors in parser output

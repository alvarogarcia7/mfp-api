# CLI Package Structure

## Overview

CLI scripts have been reorganized into logical packages:

```
backend/
├── mfp/                 # MyFitnessPal data management
│   ├── __init__.py      # Package interface
│   ├── __main__.py      # Module entry point
│   ├── fetch.py         # Download food data from MFP
│   ├── parse.py         # Process raw food data
│   └── sync.py          # Sync local entries to MFP
│
├── polar/               # Polar Flow data management
│   ├── __init__.py      # Package interface
│   ├── __main__.py      # Module entry point
│   ├── fetch.py         # Download calendar events
│   └── parse.py         # Process calendar events
│
└── main.py              # FastAPI server

cli.py                   # Unified CLI entry point (top-level)
```

## Usage

### Option 1: Unified CLI (Recommended)

Use the top-level `cli.py` script for a consistent interface:

```bash
# MyFitnessPal commands
python cli.py mfp fetch --today
python cli.py mfp fetch --last-month
python cli.py mfp fetch --since-last-entry
python cli.py mfp parse --merge
python cli.py mfp parse --replace --force
python cli.py mfp sync
python cli.py mfp sync --dry-run

# Polar Flow commands
python cli.py polar fetch --today
python cli.py polar fetch --last-month
python cli.py polar fetch --since-last-entry
python cli.py polar parse --merge
python cli.py polar parse --replace --force
```

### Option 2: Package Modules

Run packages as Python modules using `-m` flag:

```bash
# MyFitnessPal
python -m backend.mfp fetch --today
python -m backend.mfp parse --merge
python -m backend.mfp sync --dry-run

# Polar Flow
python -m backend.polar fetch --since-last-entry
python -m backend.polar parse --merge
```

### Option 3: Programmatic Import

Import modules directly in Python code:

```python
from backend.mfp import fetch as mfp_fetch
from backend.mfp import parse as mfp_parse
from backend.mfp import sync as mfp_sync

from backend.polar import fetch as polar_fetch
from backend.polar import parse as polar_parse

# Call main() or use individual functions
mfp_fetch.main()
mfp_parse.main()
mfp_sync.main()
```

## Package Details

### MFP Package (`backend/mfp/`)

**`fetch.py`** - Downloads raw food data from MyFitnessPal
- Entry point: `main()`
- Options: `--username`, `--password`, `--cookie`, `--today`, `--last-two-weeks`, `--last-month`, `--range-start`, `--range-end`
- Output: `data/raw_food_data/food_data_*.json`

**`parse.py`** - Processes raw food data into database
- Entry point: `main()`
- Options: `--file`, `--merge` (default), `--replace`, `--force`
- Output: `backend/.food_cache.json`

**`sync.py`** - Syncs local food entries to MyFitnessPal
- Entry point: `main()`
- Options: `--date`, `--all-dates`, `--mark-synced`, `--dry-run`
- Requires: MFP credentials in `.env.local`

### Polar Flow Package (`backend/polar/`)

**`fetch.py`** - Downloads calendar events from Polar Flow
- Entry point: `main()`
- Options: `--cookie`, `--today`, `--since-last-entry`, `--last-two-weeks`, `--last-month`, `--range-start`, `--range-end`
- Output: `data/raw_polar_data/polar_calendar_*.json`

**`parse.py`** - Processes calendar events into database
- Entry point: `main()`
- Options: `--file`, `--merge` (default), `--replace`, `--force`
- Output: `backend/.exercise_cache.json`

## Daily Workflow

Simple daily sync:

```bash
# Fetch and parse fresh data
python cli.py mfp fetch --since-last-entry && python cli.py mfp parse
python cli.py polar fetch --since-last-entry && python cli.py polar parse

# Use web app
python -m uvicorn backend.main:app --reload --port 8000

# Sync entries to MFP when done
python cli.py mfp sync
```

## Cron Job Examples

```bash
# Every morning at 6 AM: sync data
0 6 * * * cd /path/to/app && python cli.py mfp fetch --since-last-entry && python cli.py mfp parse

# Every evening at 8 PM: sync entries to MFP
0 20 * * * cd /path/to/app && python cli.py mfp sync

# Polar Flow (less frequent)
0 7 * * 0 cd /path/to/app && python cli.py polar fetch --since-last-entry && python cli.py polar parse
```

## Migration Guide

### From Old CLI Scripts

**Before:**
```bash
python backend/cli_fetch_food_data.py --last-month
python backend/cli_parse_food_data.py --merge
python backend/cli_sync_to_mfp.py --dry-run
python backend/cli_fetch_polar_data.py --since-last-entry
python backend/cli_parse_polar_data.py --merge
```

**After (Option 1 - Recommended):**
```bash
python cli.py mfp fetch --last-month
python cli.py mfp parse --merge
python cli.py mfp sync --dry-run
python cli.py polar fetch --since-last-entry
python cli.py polar parse --merge
```

**After (Option 2):**
```bash
python -m backend.mfp fetch --last-month
python -m backend.mfp parse --merge
python -m backend.mfp sync --dry-run
python -m backend.polar fetch --since-last-entry
python -m backend.polar parse --merge
```

## Benefits of Reorganization

✅ **Better organization** - Related functionality grouped in packages  
✅ **Easier discovery** - Clear command structure  
✅ **Programmatic access** - Can import and use modules in code  
✅ **Consistent interface** - Unified CLI with `cli.py`  
✅ **Scalability** - Easy to add new commands or packages  
✅ **Python conventions** - Follows standard package structure  

## Extending the Packages

### Adding a new MFP command

1. Create `backend/mfp/new_command.py` with `main()` function
2. Add import to `backend/mfp/__init__.py`
3. Add handler to `cli.py`
4. Update this documentation

Example:

```python
# backend/mfp/new_command.py
def main():
    parser = argparse.ArgumentParser(description="New command description")
    # ... add arguments ...
    args = parser.parse_args()
    # ... implement ...

if __name__ == "__main__":
    main()
```

Then add to `cli.py`:
```python
elif command == "new_command":
    cmd = [sys.executable, "-m", "backend.mfp.new_command"] + args
    subprocess.run(cmd)
```

## Help & Documentation

Get help for any command:

```bash
# Using unified CLI
python cli.py mfp fetch --help
python cli.py mfp parse --help
python cli.py mfp sync --help
python cli.py polar fetch --help
python cli.py polar parse --help

# Using modules directly
python -m backend.mfp.fetch --help
python -m backend.mfp.parse --help
python -m backend.polar.fetch --help
```

## Troubleshooting

### Import errors when using packages
- Ensure you're running from project root: `cd myfitnesspal-api`
- Check PYTHONPATH includes current directory
- Try using absolute path: `python -m backend.mfp fetch`

### CLI not found
- Ensure `cli.py` is executable: `chmod +x cli.py`
- Run from project root directory

### Module not found
- Check packages are properly structured with `__init__.py` files
- Verify Python version 3.10+

## API Reference

All modules export a `main()` function that can be called from Python:

```python
import sys
from backend.mfp import fetch, parse, sync
from backend.polar import fetch as polar_fetch, parse as polar_parse

# Simulate CLI arguments
sys.argv = ["script", "--today"]
fetch.main()

# Parse results
parse.main()

# Sync to MFP
sync.main()
```

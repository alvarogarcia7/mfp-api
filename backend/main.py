"""FastAPI server for MyFitnessPal web app.

Architecture:
- NO direct API calls to MFP or Polar Flow
- All data comes from local databases (.food_cache.json, .exercise_cache.json)
- Web app displays data, manages local food entries
- CLI scripts handle data acquisition and parsing
- Syncing to MFP happens via separate CLI command
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Header, Body
from fastapi.staticfiles import StaticFiles

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# In-memory food entries: {date -> {meal -> [foods]}}
_food_entries: dict = {}

# Database file paths
FOOD_DB_FILE = Path(__file__).parent / ".food_cache.json"
EXERCISE_DB_FILE = Path(__file__).parent / ".exercise_cache.json"
FOOD_SCHEMA_FILE = Path(__file__).parent / "food_schema.json"


def _load_food_cache() -> list[dict] | None:
    """Load cached food database from JSON file."""
    if not FOOD_DB_FILE.exists():
        logger.warning(f"Food cache not found: {FOOD_DB_FILE}")
        return None
    try:
        with open(FOOD_DB_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading food cache: {e}")
        return None


def _load_exercise_cache() -> list[dict] | None:
    """Load exercise database from JSON file."""
    if not EXERCISE_DB_FILE.exists():
        logger.warning(f"Exercise cache not found: {EXERCISE_DB_FILE}")
        return None
    try:
        with open(EXERCISE_DB_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading exercise cache: {e}")
        return None


def _safe_float(value) -> float:
    """Convert value to float, return 0 if None/invalid."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ============================================================================
# Status & Health Checks
# ============================================================================

@app.get("/api/status")
async def get_status():
    """Get application status and data availability."""
    food_cache = _load_food_cache()
    exercise_cache = _load_exercise_cache()

    return {
        "status": "ok",
        "mode": "offline-first",
        "data_available": {
            "food_library": bool(food_cache),
            "exercises": bool(exercise_cache),
            "food_entries": len(_food_entries) > 0,
        },
        "databases": {
            "foods": len(food_cache) if food_cache else 0,
            "exercises": len(exercise_cache) if exercise_cache else 0,
        },
        "info": "This app displays data from local databases only. Use CLI scripts to fetch/parse data."
    }


# ============================================================================
# Food Library (Read-only from local cache)
# ============================================================================

@app.get("/api/food-instances")
async def get_food_instances():
    """Get all food types from local cache.

    Returns foods from the local .food_cache.json database.
    """
    cached_foods = _load_food_cache()
    if not cached_foods:
        return {"foods": [], "count": 0}
    return {"foods": cached_foods, "count": len(cached_foods)}


# ============================================================================
# Food Entries (Local management)
# ============================================================================

@app.get("/api/food-entries")
async def get_food_entries(date_str: str | None = None):
    """Get logged food entries from local storage.

    If date_str not provided, returns entries for today.
    Format: YYYY-MM-DD
    """
    if date_str is None:
        date_str = date.today().isoformat()

    try:
        entries = _food_entries.get(date_str, {})
        return {
            "date": date_str,
            "meals": entries,
            "has_data": bool(entries)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading entries: {e}")


@app.post("/api/food-entries/add")
async def add_food_entry(request: dict = Body(...)):
    """Add a food entry to the diary (local storage only).

    Does NOT sync to MFP - use CLI command for that.
    """
    global _food_entries

    date_str = request.get("date", date.today().isoformat())
    meal = request.get("meal", "snacks")
    food_name = request.get("name")
    calories = request.get("calories", 0)
    quantity = request.get("quantity", 1.0)

    if not food_name:
        raise HTTPException(status_code=400, detail="Missing food name")

    try:
        # Initialize date/meal structure if needed
        if date_str not in _food_entries:
            _food_entries[date_str] = {
                "breakfast": [], "lunch": [], "dinner": [], "snacks": []
            }

        entry = {
            "name": food_name,
            "calories": _safe_float(calories),
            "quantity": _safe_float(quantity),
            "timestamp": date.today().isoformat()
        }

        if meal not in _food_entries[date_str]:
            _food_entries[date_str][meal] = []

        _food_entries[date_str][meal].append(entry)
        logger.info(f"Added food entry: {food_name} ({calories} cal) to {meal} on {date_str}")

        return {"success": True, "entry": entry}
    except Exception as e:
        logger.error(f"Error adding food entry: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding entry: {e}")


@app.delete("/api/food-entries/{date_str}/{meal}/{index}")
async def remove_food_entry(date_str: str, meal: str, index: int):
    """Remove a food entry from the diary (local storage only)."""
    global _food_entries

    try:
        if date_str not in _food_entries:
            raise HTTPException(status_code=404, detail="Date not found")

        if meal not in _food_entries[date_str]:
            raise HTTPException(status_code=404, detail="Meal not found")

        if index < 0 or index >= len(_food_entries[date_str][meal]):
            raise HTTPException(status_code=404, detail="Entry not found")

        entry = _food_entries[date_str][meal].pop(index)
        logger.info(f"Removed food entry: {entry.get('name')} from {meal} on {date_str}")

        return {"success": True, "removed": entry}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing food entry: {e}")
        raise HTTPException(status_code=500, detail=f"Error removing entry: {e}")


# ============================================================================
# Exercise/Activity Data (Read-only from local cache)
# ============================================================================

@app.get("/api/exercises")
async def get_exercises(date_str: str | None = None):
    """Get exercises from local cache.

    If date_str provided, filters to that date.
    Format: YYYY-MM-DD
    """
    exercise_cache = _load_exercise_cache()
    if not exercise_cache:
        return {"exercises": [], "count": 0}

    # Filter by date if specified
    if date_str:
        exercises = [e for e in exercise_cache if e.get("date") == date_str]
        return {"exercises": exercises, "count": len(exercises), "date": date_str}

    return {"exercises": exercise_cache, "count": len(exercise_cache)}


# ============================================================================
# Daily Summary (from local data only)
# ============================================================================

@app.get("/api/today")
async def get_today_summary(date_str: str | None = None):
    """Get today's summary from local data.

    Includes:
    - Food entries for the day
    - Exercise activities for the day
    - Calorie totals
    """
    if date_str is None:
        date_str = date.today().isoformat()

    try:
        # Get food entries
        food_entries = _food_entries.get(date_str, {})

        # Calculate food totals
        total_calories = 0.0
        total_protein = 0.0
        total_carbs = 0.0
        total_fat = 0.0

        for meal_entries in food_entries.values():
            for entry in meal_entries:
                total_calories += _safe_float(entry.get("calories"))
                total_protein += _safe_float(entry.get("protein", 0))
                total_carbs += _safe_float(entry.get("carbs", 0))
                total_fat += _safe_float(entry.get("fat", 0))

        # Get exercises for the day
        exercise_cache = _load_exercise_cache()
        day_exercises = []
        exercise_calories = 0.0
        if exercise_cache:
            day_exercises = [e for e in exercise_cache if e.get("date") == date_str]
            for exercise in day_exercises:
                exercise_calories += _safe_float(exercise.get("calories", 0))

        return {
            "date": date_str,
            "goal_calories": 2000,  # Default, could be configurable
            "calories_eaten": int(total_calories),
            "exercise_calories": int(exercise_calories),
            "remaining": int(2000 - total_calories + exercise_calories),
            "macros": {
                "protein": int(total_protein),
                "carbs": int(total_carbs),
                "fat": int(total_fat),
            },
            "meals": food_entries,
            "exercises": day_exercises,
        }
    except Exception as e:
        logger.error(f"Error getting today's summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {e}")


# ============================================================================
# Static Files
# ============================================================================

import pathlib

static_dir = pathlib.Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


# ============================================================================
# Startup Messages
# ============================================================================

@app.on_event("startup")
async def startup():
    """Startup messages."""
    logger.info("=" * 70)
    logger.info("MyFitnessPal Web App - Offline-First Mode")
    logger.info("=" * 70)
    logger.info("")
    logger.info("🔑 Key Points:")
    logger.info("  • Web app ONLY displays data from local databases")
    logger.info("  • NO direct API calls to MyFitnessPal or Polar Flow")
    logger.info("  • Data acquisition: use CLI scripts")
    logger.info("    - cli_fetch_food_data.py (download from MFP)")
    logger.info("    - cli_parse_food_data.py (process to database)")
    logger.info("    - cli_fetch_polar_data.py (download from Polar Flow)")
    logger.info("    - cli_parse_polar_data.py (process to database)")
    logger.info("  • Syncing to MFP: use CLI script")
    logger.info("    - cli_sync_to_mfp.py (sync local entries to MFP)")
    logger.info("")
    logger.info("📊 Available Data:")

    food_cache = _load_food_cache()
    exercise_cache = _load_exercise_cache()

    if food_cache:
        logger.info(f"  ✅ Food Library: {len(food_cache)} foods")
    else:
        logger.info(f"  ⚠️  Food Library: not loaded (run cli_fetch_food_data.py + cli_parse_food_data.py)")

    if exercise_cache:
        logger.info(f"  ✅ Exercises: {len(exercise_cache)} activities")
    else:
        logger.info(f"  ⚠️  Exercises: not loaded (run cli_fetch_polar_data.py + cli_parse_polar_data.py)")

    logger.info("")
    logger.info("🌐 Web App running at: http://localhost:8000")
    logger.info("=" * 70)

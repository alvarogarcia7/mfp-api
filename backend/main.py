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
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Header, Body
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

import sys
import importlib.util

# Import diary modules without triggering mfp package __init__
mfp_dir = Path(__file__).parent / "mfp"
spec_repo = importlib.util.spec_from_file_location("diary_repository", mfp_dir / "diary_repository.py")
diary_repo_module = importlib.util.module_from_spec(spec_repo)
spec_repo.loader.exec_module(diary_repo_module)
DiaryRepository = diary_repo_module.DiaryRepository

spec_sched = importlib.util.spec_from_file_location("meal_schedule", mfp_dir / "meal_schedule.py")
meal_sched_module = importlib.util.module_from_spec(spec_sched)
spec_sched.loader.exec_module(meal_sched_module)
MealSchedule = meal_sched_module.MealSchedule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# ============================================================================
# Pydantic Models
# ============================================================================

class ExerciseCreate(BaseModel):
    """Exercise creation request model."""
    date: str
    name: str
    calories: int
    duration: int
    distance: float = 0.0


# In-memory food entries: {date -> {meal -> [foods]}}
# Loaded from disk on startup
_food_entries: dict = {}

# Database file paths
FOOD_DB_FILE = Path(__file__).parent / ".food_cache.json"
EXERCISE_DB_FILE = Path(__file__).parent / "polar" / ".exercise_cache.json"
DIARY_DB_FILE = Path(__file__).parent / ".diary_cache.json"
FOOD_ENTRIES_FILE = Path(__file__).parent / ".food_entries.json"
USER_PROFILE_FILE = Path(__file__).parent / "data" / "user" / "profile.json"
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


def _save_exercise_cache(exercises: list[dict]) -> None:
    """Save exercise database to JSON file."""
    try:
        # Ensure directory exists
        EXERCISE_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EXERCISE_DB_FILE, 'w') as f:
            json.dump(exercises, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving exercise cache: {e}")


def _safe_float(value) -> float:
    """Convert value to float, return 0 if None/invalid."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _load_food_entries() -> dict:
    """Load food entries from disk."""
    if not FOOD_ENTRIES_FILE.exists():
        return {}
    try:
        with open(FOOD_ENTRIES_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading food entries: {e}")
        return {}


def _save_food_entries(entries: dict) -> None:
    """Save food entries to disk."""
    try:
        with open(FOOD_ENTRIES_FILE, 'w') as f:
            json.dump(entries, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving food entries: {e}")


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


@app.get("/api/polar-flow/status")
async def get_polar_flow_status():
    """Get Polar Flow connection status.

    Returns information about exercise data availability.
    """
    exercise_cache = _load_exercise_cache()
    has_exercises = bool(exercise_cache)
    exercise_count = len(exercise_cache) if exercise_cache else 0

    return {
        "connected": has_exercises,
        "configured": True,  # We support offline-first mode
        "username": "Local Database",
        "message": f"✅ {exercise_count} exercises available in local database" if has_exercises else "⚠️ No exercises loaded yet. Run 'make polar-download && make polar-parse' to import exercises.",
        "exercises_available": exercise_count
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
    """Add a food entry to local storage.

    Entry is persisted to disk. Backend will sync to MFP via /api/food-entries/sync.
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
            "timestamp": date.today().isoformat(),
            "replicatedToMFP": False
        }

        if meal not in _food_entries[date_str]:
            _food_entries[date_str][meal] = []

        _food_entries[date_str][meal].append(entry)
        _save_food_entries(_food_entries)
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
# Diary Cache (Read-only from local cache)
# ============================================================================

@app.get("/api/diary-entries")
async def get_diary_entries(date_str: str | None = None):
    """Get diary entries from local diary cache.

    If date_str not provided, returns entries for today.
    Format: YYYY-MM-DD
    """
    if date_str is None:
        date_str = date.today().isoformat()

    try:
        repo = DiaryRepository(DIARY_DB_FILE)
        target_date = date.fromisoformat(date_str)
        entry = repo.load_entries_for_date(target_date)

        if not entry:
            return {
                "date": date_str,
                "meals": {"breakfast": [], "lunch": [], "dinner": [], "snacks": []},
                "totals": {},
                "has_data": False
            }

        return {
            "date": date_str,
            "meals": entry.get("meals", {}),
            "totals": entry.get("totals", {}),
            "metadata": entry.get("metadata", {}),
            "has_data": True
        }
    except Exception as e:
        logger.error(f"Error loading diary entries: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading entries: {e}")


@app.get("/api/meal-schedule")
async def get_meal_schedule():
    """Get meal schedule configuration and current meal.

    Returns the hardcoded meal schedule and what meal is current.
    """
    try:
        current_meal = MealSchedule.get_current_meal()
        schedule_info = MealSchedule.get_schedule_info()

        return {
            "current_meal": current_meal,
            "schedule": schedule_info
        }
    except Exception as e:
        logger.error(f"Error getting meal schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@app.get("/api/user-goals")
async def get_user_goals():
    """Get user's daily nutritional goals from profile.

    Returns daily calorie goal, macro targets, and other goals.
    """
    try:
        if not USER_PROFILE_FILE.exists():
            # Return default goals if profile not set up
            return {
                "calories": 2000,
                "protein": 50,
                "carbohydrates": 300,
                "fat": 65,
                "fiber": 25,
                "sodium": 2300,
                "sugar": 50,
                "cholesterol": 300,
                "saturated_fat": 20,
            }

        with open(USER_PROFILE_FILE, 'r') as f:
            profile = json.load(f)

        goals = profile.get("goals", {})
        # Extract values from goal objects {value: X, unit: Y}
        return {
            "calories": goals.get("calories", {}).get("value", 2000),
            "protein": goals.get("protein", {}).get("value", 50),
            "carbohydrates": goals.get("carbohydrates", {}).get("value", 300),
            "fat": goals.get("fat", {}).get("value", 65),
            "fiber": goals.get("fiber", {}).get("value", 25),
            "sodium": goals.get("sodium", {}).get("value", 2300),
            "sugar": goals.get("sugar", {}).get("value", 50),
            "cholesterol": goals.get("cholesterol", {}).get("value", 300),
            "saturated_fat": goals.get("saturated_fat", {}).get("value", 20),
        }
    except Exception as e:
        logger.error(f"Error getting user goals: {e}")
        # Return defaults on error
        return {
            "calories": 2000,
            "protein": 50,
            "carbohydrates": 300,
            "fat": 65,
            "fiber": 25,
            "sodium": 2300,
            "sugar": 50,
            "cholesterol": 300,
            "saturated_fat": 20,
        }


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


@app.post("/api/exercises/add")
async def add_exercise(exercise: ExerciseCreate):
    """Add a quick exercise entry to the database."""
    try:
        # Validate inputs
        if not exercise.date or not exercise.name:
            raise HTTPException(status_code=400, detail="date and name are required")
        if exercise.calories <= 0:
            raise HTTPException(status_code=400, detail="calories must be positive")
        if exercise.duration <= 0:
            raise HTTPException(status_code=400, detail="duration must be positive")

        # Load existing exercises
        exercises = _load_exercise_cache() or []

        # Create new exercise entry
        new_exercise = {
            "date": exercise.date,
            "name": exercise.name,
            "calories": exercise.calories,
            "duration": exercise.duration,
            "distance": exercise.distance,
            "created_at": datetime.now().isoformat()
        }

        # Add to list
        exercises.append(new_exercise)

        # Save back to file
        _save_exercise_cache(exercises)

        logger.info(f"✅ Added exercise: {exercise.name} on {exercise.date} ({exercise.calories} kcal, {exercise.duration} min)")
        return {
            "status": "success",
            "exercise": new_exercise,
            "total_exercises": len(exercises)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding exercise: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    """Startup messages and initialization."""
    global _food_entries

    # Load food entries from disk
    _food_entries = _load_food_entries()

    logger.info("=" * 70)
    logger.info("MyFitnessPal Web App - Offline-First Mode")
    logger.info("=" * 70)
    logger.info("")
    logger.info("🔑 Key Points:")
    logger.info("  • Web app adds food entries locally")
    logger.info("  • Backend syncs entries to MyFitnessPal")
    logger.info("  • NO direct API calls from frontend to MFP")
    logger.info("  • Data acquisition: use CLI scripts or web app")
    logger.info("    - Web app: add foods via UI (stored locally, backend syncs)")
    logger.info("    - CLI: cli_fetch_food_data.py (download MFP library)")
    logger.info("    - CLI: cli_fetch_diary_data.py (download MFP diary)")
    logger.info("  • Syncing to MFP: automatic via backend endpoint or CLI")
    logger.info("    - POST /api/food-entries/sync (backend sync)")
    logger.info("    - CLI: sync.py (alternative)")
    logger.info("")
    logger.info("📊 Available Data:")

    food_cache = _load_food_cache()
    exercise_cache = _load_exercise_cache()
    food_entries_count = len([e for meals in _food_entries.values() for e in sum(meals.values(), [])])

    if food_cache:
        logger.info(f"  ✅ Food Library: {len(food_cache)} foods")
    else:
        logger.info(f"  ⚠️  Food Library: not loaded")

    if exercise_cache:
        logger.info(f"  ✅ Exercises: {len(exercise_cache)} activities")
    else:
        logger.info(f"  ⚠️  Exercises: not loaded")

    if food_entries_count > 0:
        logger.info(f"  ✅ Local Entries: {food_entries_count} foods (pending sync)")
    else:
        logger.info(f"  ℹ️  Local Entries: empty")

    logger.info("")
    logger.info("🌐 Web App running at: http://localhost:8000")
    logger.info("=" * 70)

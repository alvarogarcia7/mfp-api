"""FastAPI server for MyFitnessPal web app."""

import asyncio
import json
import logging
import uuid
from datetime import date
from pathlib import Path
from typing import Annotated
import os

from fastapi import FastAPI, HTTPException, Header, Depends, Body
from fastapi.staticfiles import StaticFiles
from jsonschema import validate, ValidationError
from dotenv import load_dotenv

from vendor import mfp_client, diary
from mfp_auth import login_mfp_password, login_mfp_cookie
from polar_flow import create_polar_client

# Load environment variables from .env.local
load_dotenv(Path(__file__).parent.parent / ".env.local")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# In-memory session storage: session_id -> CurlCffiClient
_sessions: dict[str, mfp_client.CurlCffiClient] = {}

# Current logged-in user (optional, None for offline mode)
_current_user: dict | None = None

# In-memory food entries: {date -> {meal -> [foods]}}
_food_entries: dict = {}

# Polar Flow integration
_polar_flow_client = None
_polar_flow_activities: dict = {}  # Cached activities by date

# Food database file path
FOOD_DB_FILE = Path(__file__).parent / ".food_cache.json"

# Food schema file path
FOOD_SCHEMA_FILE = Path(__file__).parent / "food_schema.json"

# Entries file path
ENTRIES_DIR = Path(__file__).parent.parent / "data" / "food"
ENTRIES_FILE = ENTRIES_DIR / "entries.json"

# Credentials file path
CREDENTIALS_DIR = Path(__file__).parent.parent / "data" / "user"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"

# Load food schema at startup
_food_schema = None

def _load_food_schema() -> dict:
    """Load and cache the food schema."""
    global _food_schema
    if _food_schema is not None:
        return _food_schema

    try:
        with open(FOOD_SCHEMA_FILE, 'r') as f:
            _food_schema = json.load(f)
        logger.info("Loaded food schema")
        return _food_schema
    except Exception as e:
        logger.error(f"Failed to load food schema: {e}")
        raise RuntimeError(f"Cannot start without food schema: {e}")


def get_session_id(authorization: Annotated[str | None, Header()] = None) -> str | None:
    """Extract session ID from Authorization header.

    Returns None if not provided (offline/local mode).
    """
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    return authorization[7:]


def get_client(session_id: str | None) -> mfp_client.CurlCffiClient | None:
    """Look up client from session ID.

    Returns None if no session (offline mode).
    """
    if session_id is None:
        return None
    if session_id not in _sessions:
        raise HTTPException(status_code=401, detail="Session expired")
    return _sessions[session_id]


@app.post("/api/login")
async def login(request: dict = Body(...)):
    """Login with username/password or session cookie, return session ID.

    Supports two methods:
    1. Username/Password: {"username": "...", "password": "..."}
    2. Session Cookie: {"cookie": "..."}

    Cookie can be:
    - Raw token: abc123def456...
    - Cookie header: __Secure-next-auth.session-token=abc123; ...
    - Full header: Cookie: __Secure-next-auth.session-token=abc123; ...
    """
    logger.info(f"Login request received: {list(request.keys())}")

    username = request.get("username")
    password = request.get("password")
    cookie_input = request.get("cookie")

    # Validate inputs
    if not username and not password and not cookie_input:
        logger.warning("Login attempted with no credentials")
        raise HTTPException(
            status_code=400,
            detail="Provide either username/password or session cookie"
        )

    if cookie_input:
        logger.info("Attempting cookie-based login")
        if not username:
            logger.warning("Cookie login attempted without username")
            raise HTTPException(status_code=400, detail="Username required for cookie login")
        try:
            cookies, mfp_username = await asyncio.to_thread(
                login_mfp_cookie, cookie_input, username
            )
            logger.info(f"Cookie login successful for: {mfp_username}")
        except ValueError as e:
            logger.error(f"Cookie login failed: {e}")
            raise HTTPException(status_code=401, detail=str(e))
        except Exception as e:
            logger.error(f"Cookie login error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Cookie login error: {e}")

    elif username and password:
        logger.info(f"Attempting password login for: {username}")
        if not username or not password:
            logger.warning("Password login attempted with missing fields")
            raise HTTPException(status_code=400, detail="Missing username or password")

        try:
            cookies, mfp_username = await asyncio.to_thread(
                login_mfp_password, username, password
            )
            logger.info(f"Password login successful for: {mfp_username}")
        except ValueError as e:
            logger.error(f"Password login failed: {e}")
            raise HTTPException(status_code=401, detail=str(e))
        except Exception as e:
            logger.error(f"Password login error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Login error: {e}")
    else:
        logger.warning("Incomplete login credentials")
        raise HTTPException(
            status_code=400,
            detail="Provide complete username/password or a valid cookie"
        )

    # Create session and store client
    session_id = str(uuid.uuid4())
    logger.debug(f"Creating session: {session_id}")

    try:
        client = mfp_client.build_client(cookies, username=mfp_username)
        logger.debug(f"Built MFP client for: {mfp_username}")
    except Exception as e:
        logger.error(f"Failed to build MFP client: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail=f"Auth failed: {e}")

    _sessions[session_id] = client

    # Set current user (global state for logged-in mode)
    global _current_user
    _current_user = {
        "session_id": session_id,
        "username": mfp_username,
        "logged_in": True
    }

    logger.info(f"Session created: {session_id} for user: {mfp_username}")

    # Save credentials to disk
    try:
        if cookie_input:
            _save_credentials(mfp_username, password=None, cookie=cookie_input)
        else:
            _save_credentials(mfp_username, password=password, cookie=None)
    except Exception as e:
        logger.warning(f"Failed to save credentials: {e}")

    return {"session_id": session_id, "username": mfp_username}


@app.get("/api/status")
async def get_status():
    """Get application status: logged in or offline mode."""
    global _current_user
    if _current_user:
        return {
            "logged_in": True,
            "username": _current_user.get("username"),
            "mode": "online"
        }
    else:
        return {
            "logged_in": False,
            "username": None,
            "mode": "offline"
        }


@app.post("/api/logout")
async def logout(session_id: str = Depends(get_session_id)):
    """Clear session and switch to offline mode."""
    if session_id:
        _sessions.pop(session_id, None)

    global _current_user
    _current_user = None
    return {"status": "logged out"}


@app.get("/api/today")
async def get_today(session_id: str = Depends(get_session_id)):
    """Get today's diary summary."""
    client = get_client(session_id)

    def fetch_data():
        mfp_day = client.get_date(date.today())

        # Parse meals with comprehensive nutrition data
        meals = {}
        for meal in mfp_day.meals:
            meal_name = meal.name.lower()
            meals[meal_name] = []
            for entry in meal.entries:
                meals[meal_name].append(_extract_entry_data(entry))

        # Get exercise calories
        exercise_calories = 0.0
        try:
            exercise_data = diary.get_exercise(client, date.today())
            if exercise_data.get("exercise"):
                for section, entries in exercise_data["exercise"].items():
                    for entry in entries:
                        if isinstance(entry, dict) and "calories" in entry:
                            exercise_calories += _safe_float(entry.get("calories", 0))
        except Exception:
            pass

        return {
            "date": date.today().isoformat(),
            "goal_calories": _safe_float(mfp_day.goals.get("calories")) if mfp_day.goals else 2000,
            "calories_eaten": _safe_float(mfp_day.totals.get("calories")),
            "exercise_calories": exercise_calories,
            "remaining": (_safe_float(mfp_day.goals.get("calories")) if mfp_day.goals else 2000) - _safe_float(mfp_day.totals.get("calories")) + exercise_calories,
            "meals": meals,
        }

    try:
        result = await asyncio.to_thread(fetch_data)

        # Save entries to in-memory storage (offline mode)
        today_str = date.today().isoformat()
        global _food_entries
        _food_entries[today_str] = result.get("meals", {})

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fetch error: {e}")


@app.post("/api/search")
async def search(request: dict = Body(...), session_id: str = Depends(get_session_id)):
    """Search for foods."""
    query = request.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Missing query")

    client = get_client(session_id)

    def search_foods():
        return diary.search_food(client, query, limit=5, with_macros=True)

    try:
        results = await asyncio.to_thread(search_foods)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {e}")


@app.get("/api/csrf")
async def get_csrf(session_id: str = Depends(get_session_id)):
    """Get CSRF token for batch operations."""
    client = get_client(session_id)

    def fetch_csrf():
        doc, token = diary.diary_page(client, date.today())
        return token

    try:
        csrf = await asyncio.to_thread(fetch_csrf)
        return {"csrf": csrf}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSRF fetch error: {e}")


@app.post("/api/log")
async def log_food(request: dict = Body(...), session_id: str = Depends(get_session_id)):
    """Log food to diary.

    Optionally accepts a pre-fetched CSRF token to avoid redundant requests.
    If csrf is not provided, fetches it from the diary page.
    """
    client = get_client(session_id)

    food_id = request.get("food_id")
    weight_id = request.get("weight_id")
    quantity = request.get("quantity", 1.0)
    meal = request.get("meal", "breakfast")
    csrf = request.get("csrf")

    if not food_id or not weight_id:
        raise HTTPException(status_code=400, detail="Missing food_id or weight_id")

    def log_it():
        nonlocal csrf
        if not csrf:
            doc, csrf = diary.diary_page(client, date.today())
        return diary.add_food_to_diary(
            client,
            food_id,
            weight_id,
            csrf,
            meal,
            date.today(),
            float(quantity),
        )

    try:
        result = await asyncio.to_thread(log_it)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Log error: {e}")


@app.delete("/api/entry/{entry_id}")
async def delete_entry(entry_id: str, session_id: str = Depends(get_session_id)):
    """Delete a diary entry."""
    client = get_client(session_id)

    def delete_it():
        doc, token = diary.diary_page(client, date.today())
        diary.remove_entry(client, entry_id, token)

    try:
        await asyncio.to_thread(delete_it)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete error: {e}")


def _safe_float(value) -> float:
    """Convert value to float, return 0 if None/invalid."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _load_food_cache() -> list[dict] | None:
    """Load cached food database from JSON file."""
    if not FOOD_DB_FILE.exists():
        return None
    try:
        with open(FOOD_DB_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading food cache: {e}")
        return None


def _validate_food(food: dict, index: int = None) -> bool:
    """Validate a food item against the schema.

    Raises ValidationError if the food doesn't match the schema.
    """
    schema = _load_food_schema()
    try:
        validate(instance=food, schema=schema)
        return True
    except ValidationError as e:
        prefix = f"Food {index}: " if index is not None else ""
        logger.error(f"{prefix}Validation error: {e.message}")
        raise


def _save_food_cache(foods: list[dict]) -> None:
    """Save food database to JSON file, validating each item first."""
    try:
        # Validate all foods before saving
        for idx, food in enumerate(foods):
            _validate_food(food, index=idx)

        with open(FOOD_DB_FILE, 'w') as f:
            json.dump(foods, f, indent=2)
        logger.info(f"Saved {len(foods)} foods to cache file (all validated)")
    except ValidationError as e:
        logger.error(f"Food cache save failed: validation error - {e.message}")
        raise
    except Exception as e:
        logger.error(f"Error saving food cache: {e}")
        raise


def _load_entries() -> dict:
    """Load diary entries from JSON file."""
    if not ENTRIES_FILE.exists():
        return {"last_updated": None, "entries": []}
    try:
        with open(ENTRIES_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading entries: {e}")
        return {"last_updated": None, "entries": []}


def _save_entries(entries_data: dict) -> None:
    """Save diary entries to JSON file, validating food items first."""
    try:
        # Validate all food items in entries
        for entry_idx, entry in enumerate(entries_data.get("entries", [])):
            for meal_name, meal_foods in entry.get("meals", {}).items():
                for food_idx, food in enumerate(meal_foods):
                    _validate_food(food, index=f"entry[{entry_idx}].meals[{meal_name}][{food_idx}]")

        ENTRIES_DIR.mkdir(parents=True, exist_ok=True)
        with open(ENTRIES_FILE, 'w') as f:
            json.dump(entries_data, f, indent=2)
        logger.info(f"Saved entries to {ENTRIES_FILE} (all validated)")
    except ValidationError as e:
        logger.error(f"Entries save failed: validation error - {e.message}")
        raise
    except Exception as e:
        logger.error(f"Error saving entries: {e}")
        raise


def _load_credentials() -> dict:
    """Load credentials from JSON file."""
    if not CREDENTIALS_FILE.exists():
        return {"last_login": None, "username": None, "password": None, "cookie": None}
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading credentials: {e}")
        return {"last_login": None, "username": None, "password": None, "cookie": None}


def _save_credentials(username: str, password: str | None = None, cookie: str | None = None) -> None:
    """Save credentials to JSON file.

    WARNING: Storing passwords in plaintext is a security risk.
    This should only be used for local development/testing.
    """
    try:
        from datetime import datetime
        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

        credentials_data = {
            "last_login": datetime.now().isoformat(),
            "username": username,
            "password": password,
            "cookie": cookie,
        }

        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(credentials_data, f, indent=2)

        logger.info(f"Saved credentials for user: {username}")
        logger.warning("⚠️  WARNING: Credentials stored in plaintext. This is only for development/testing!")
    except Exception as e:
        logger.error(f"Error saving credentials: {e}")


def _extract_entry_data(entry) -> dict:
    """Extract all available information from a food entry."""
    totals = entry.totals if hasattr(entry, 'totals') else {}

    entry_data = {
        "name": entry.name,
        "calories": _safe_float(totals.get("calories")),
        "protein": _safe_float(totals.get("protein")),
        "carbs": _safe_float(totals.get("carbohydrates")),
        "fat": _safe_float(totals.get("fat")),
        "fiber": _safe_float(totals.get("fiber")),
        "sugar": _safe_float(totals.get("sugar")),
        "sodium": _safe_float(totals.get("sodium")),
        "cholesterol": _safe_float(totals.get("cholesterol")),
        "saturated_fat": _safe_float(totals.get("saturated_fat")),
        "potassium": _safe_float(totals.get("potassium")),
    }

    # Add entry ID if available
    if hasattr(entry, 'id'):
        entry_data["entry_id"] = entry.id
    elif hasattr(entry, 'identifier'):
        entry_data["entry_id"] = entry.identifier

    # Add serving size info if available
    if hasattr(entry, 'serving_size'):
        entry_data["serving_size"] = entry.serving_size
    if hasattr(entry, 'serving_unit'):
        entry_data["serving_unit"] = entry.serving_unit
    if hasattr(entry, 'quantity'):
        entry_data["quantity"] = _safe_float(entry.quantity)

    return entry_data


def _fetch_foods_for_range(client, start_date: date, end_date: date) -> list[dict]:
    """Fetch unique foods from diary entries in a date range."""
    from datetime import timedelta

    foods_map = {}  # Use dict to deduplicate by food name

    # Fetch diary entries for the date range
    current = end_date
    while current >= start_date:
        try:
            mfp_day = client.get_date(current)

            for meal in mfp_day.meals:
                for entry in meal.entries:
                    name = entry.name
                    calories = _safe_float(entry.totals.get("calories"))
                    protein = _safe_float(entry.totals.get("protein"))
                    carbs = _safe_float(entry.totals.get("carbohydrates"))
                    fat = _safe_float(entry.totals.get("fat"))

                    # Skip if already have this food (take first occurrence)
                    if name not in foods_map:
                        foods_map[name] = {
                            "name": name,
                            "calories": calories,
                            "protein": protein,
                            "carbs": carbs,
                            "fat": fat,
                            "unit": "g",  # All foods stored in grams
                        }
        except Exception as e:
            logger.warning(f"Error fetching diary for {current}: {e}")

        current -= timedelta(days=1)

    return list(foods_map.values())


@app.get("/api/foods/recent")
async def get_recent_foods(session_id: str = Depends(get_session_id)):
    """Get cached food database, or fetch from MFP if not cached.

    Fetches from diary entries in the last 7 days and caches to JSON file.
    Returns a list of unique foods with standardized measurements (grams/ml).
    """
    # Try to load from cache first
    cached_foods = _load_food_cache()
    if cached_foods is not None:
        logger.info(f"Returning cached food database: {len(cached_foods)} foods")
        return {"foods": cached_foods, "cached": True}

    # Only fetch from MFP if cache doesn't exist
    client = get_client(session_id)
    from datetime import timedelta

    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        foods = await asyncio.to_thread(_fetch_foods_for_range, client, start_date, end_date)
        logger.info(f"Fetched {len(foods)} unique foods from last 7 days")

        # Save to cache for future use
        _save_food_cache(foods)

        return {"foods": foods, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching recent foods: {e}")


@app.get("/api/foods/range")
async def get_foods_for_range(
    start_date: str,
    end_date: str,
    session_id: str = Depends(get_session_id)
):
    """Fetch foods from a custom date range (format: YYYY-MM-DD).

    Does not use or update the cache. Useful for loading additional foods.
    """
    client = get_client(session_id)

    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        if start > end:
            raise HTTPException(status_code=400, detail="start_date must be before end_date")

        logger.info(f"Fetching foods from {start} to {end}")
        foods = await asyncio.to_thread(_fetch_foods_for_range, client, start, end)
        logger.info(f"Fetched {len(foods)} foods for range {start} to {end}")

        return {"foods": foods, "date_range": {"start": start_date, "end": end_date}}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching foods: {e}")


@app.get("/api/food-instances")
async def get_food_instances():
    """Get all food types in the cache (not entries, but unique foods).

    Returns foods from the local cache database.
    """
    try:
        cached_foods = _load_food_cache()
        if not cached_foods:
            return {"foods": [], "count": 0}
        return {"foods": cached_foods, "count": len(cached_foods)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading foods: {e}")


@app.get("/api/food-entries")
async def get_food_entries(date_str: str | None = None):
    """Get logged food entries from in-memory storage.

    If date_str not provided, returns entries for today.
    Format: YYYY-MM-DD
    """
    global _food_entries

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
async def add_food_entry(request: dict = Body(...), session_id: str = Depends(get_session_id)):
    """Add a food entry to today's log.

    Works both online (syncs to MFP) and offline (stores locally).
    """
    global _food_entries

    date_str = request.get("date", date.today().isoformat())
    meal = request.get("meal", "snacks")
    food_id = request.get("food_id")
    weight_id = request.get("weight_id")
    quantity = request.get("quantity", 1.0)

    if not food_id or not weight_id:
        raise HTTPException(status_code=400, detail="Missing food_id or weight_id")

    try:
        # Online mode: sync with MFP
        if session_id:
            client = get_client(session_id)
            if client:
                def log_to_mfp():
                    csrf = request.get("csrf")
                    if not csrf:
                        _, csrf = diary.diary_page(client, date.fromisoformat(date_str))
                    return diary.add_food_to_diary(
                        client, food_id, weight_id, csrf, meal,
                        date.fromisoformat(date_str), float(quantity)
                    )
                await asyncio.to_thread(log_to_mfp)

        # Store entry in local memory
        if date_str not in _food_entries:
            _food_entries[date_str] = {
                "breakfast": [], "lunch": [], "dinner": [], "snacks": []
            }

        entry = {
            "name": request.get("name", f"Food {food_id}"),
            "calories": request.get("calories", 0),
            "quantity": quantity,
            "food_id": food_id,
            "weight_id": weight_id,
            "timestamp": date.today().isoformat()
        }

        if meal not in _food_entries[date_str]:
            _food_entries[date_str][meal] = []

        _food_entries[date_str][meal].append(entry)
        logger.info(f"Added food entry: {entry['name']} to {meal} on {date_str}")

        return {"success": True, "entry": entry}
    except Exception as e:
        logger.error(f"Error adding food entry: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding entry: {e}")


# ============================================================================
# POLAR FLOW INTEGRATION
# ============================================================================

@app.get("/api/polar-flow/status")
async def get_polar_flow_status():
    """Check if Polar Flow is configured and connected."""
    global _polar_flow_client

    polar_username = os.getenv("POLAR_FLOW_USERNAME")
    polar_cookie = os.getenv("POLAR_FLOW_COOKIE")

    if not polar_username or not polar_cookie:
        return {
            "connected": False,
            "configured": False,
            "message": "Polar Flow credentials not found in .env.local"
        }

    if _polar_flow_client is None:
        try:
            _polar_flow_client = create_polar_client(polar_cookie, polar_username)
            if not _polar_flow_client.validate_connection():
                return {
                    "connected": False,
                    "configured": True,
                    "message": "Invalid Polar Flow credentials"
                }
        except Exception as e:
            logger.error(f"Error connecting to Polar Flow: {e}")
            return {
                "connected": False,
                "configured": True,
                "message": f"Connection error: {e}"
            }

    return {
        "connected": True,
        "configured": True,
        "username": os.getenv("POLAR_FLOW_USERNAME"),
        "message": "Connected to Polar Flow"
    }


@app.get("/api/polar-flow/activities")
async def get_polar_flow_activities(
    start_date: str,
    end_date: str,
    session_id: str = Depends(get_session_id)
):
    """Fetch activities from Polar Flow for a date range.

    Format: YYYY-MM-DD
    """
    global _polar_flow_client, _polar_flow_activities

    if _polar_flow_client is None:
        polar_username = os.getenv("POLAR_FLOW_USERNAME")
        polar_cookie = os.getenv("POLAR_FLOW_COOKIE")

        if not polar_username or not polar_cookie:
            raise HTTPException(
                status_code=400,
                detail="Polar Flow not configured. Add credentials to .env.local"
            )

        try:
            _polar_flow_client = create_polar_client(polar_cookie, polar_username)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Polar Flow connection error: {e}")

    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        if start > end:
            raise HTTPException(status_code=400, detail="start_date must be before end_date")

        logger.info(f"Fetching Polar Flow activities from {start} to {end}")

        def fetch_activities():
            return _polar_flow_client.get_activities(start, end)

        activities = await asyncio.to_thread(fetch_activities)

        # Cache activities by date
        for activity in activities:
            activity_date = activity.get("date")
            if activity_date not in _polar_flow_activities:
                _polar_flow_activities[activity_date] = []
            _polar_flow_activities[activity_date].append(activity)

        logger.info(f"Fetched {len(activities)} activities from Polar Flow")

        return {
            "activities": activities,
            "count": len(activities),
            "date_range": {"start": start_date, "end": end_date}
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error fetching Polar Flow activities: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching activities: {e}")


@app.post("/api/polar-flow/sync-to-mfp")
async def sync_polar_activities_to_mfp(
    request: dict = Body(...),
    session_id: str = Depends(get_session_id)
):
    """Sync selected Polar Flow activities to MFP as cardio exercises.

    Request body:
    {
        "activities": [
            {
                "date": "2026-09-15",
                "name": "Polar Flow - Running",
                "duration_minutes": 30,
                "calories": 300
            }
        ]
    }
    """
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Must be logged into MFP to sync activities"
        )

    client = get_client(session_id)
    if not client:
        raise HTTPException(
            status_code=401,
            detail="Not logged into MFP"
        )

    activities = request.get("activities", [])
    if not activities:
        raise HTTPException(status_code=400, detail="No activities to sync")

    synced = []
    errors = []

    try:
        for activity in activities:
            try:
                activity_date = date.fromisoformat(activity.get("date", ""))
                duration_minutes = activity.get("duration_minutes", 0)
                calories = activity.get("calories", 0)
                name = activity.get("name", "Cardio Activity")

                if not duration_minutes or not calories:
                    errors.append(f"{name}: missing duration or calories")
                    continue

                logger.info(f"Syncing {name} ({duration_minutes}min, {calories}cal) to MFP")

                def add_exercise():
                    """Add exercise to MFP diary."""
                    doc, csrf = diary.diary_page(client, activity_date)
                    # Add as note since we don't have direct exercise API
                    # Format: "Activity: X minutes, Y calories"
                    note_text = f"{name}: {duration_minutes} minutes, {int(calories)} calories"
                    diary.set_note(client, activity_date, note_text)

                await asyncio.to_thread(add_exercise)
                synced.append({
                    "name": name,
                    "date": activity.get("date"),
                    "duration_minutes": duration_minutes,
                    "calories": calories
                })

            except Exception as e:
                logger.error(f"Error syncing activity: {e}")
                errors.append(f"{activity.get('name', 'Unknown')}: {str(e)}")

        return {
            "synced": synced,
            "synced_count": len(synced),
            "errors": errors,
            "error_count": len(errors)
        }

    except Exception as e:
        logger.error(f"Error in sync operation: {e}")
        raise HTTPException(status_code=500, detail=f"Sync error: {e}")


# Mount static files (frontend)
import pathlib
static_dir = pathlib.Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

"""FastAPI server for MyFitnessPal web app."""

import asyncio
import json
import logging
import uuid
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Header, Depends, Body
from fastapi.staticfiles import StaticFiles

from vendor import mfp_client, diary
from mfp_auth import login_mfp_password, login_mfp_cookie

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# In-memory session storage: session_id -> CurlCffiClient
_sessions: dict[str, mfp_client.CurlCffiClient] = {}

# Food database file path
FOOD_DB_FILE = Path(__file__).parent / ".food_cache.json"


def get_session_id(authorization: Annotated[str | None, Header()] = None) -> str:
    """Extract session ID from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    return authorization[7:]


def get_client(session_id: str) -> mfp_client.CurlCffiClient:
    """Look up client from session ID."""
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
    logger.info(f"Session created: {session_id} for user: {mfp_username}")

    return {"session_id": session_id, "username": mfp_username}


@app.post("/api/logout")
async def logout(session_id: str = Depends(get_session_id)):
    """Clear session."""
    _sessions.pop(session_id, None)
    return {}


@app.get("/api/today")
async def get_today(session_id: str = Depends(get_session_id)):
    """Get today's diary summary."""
    client = get_client(session_id)

    def fetch_data():
        mfp_day = client.get_date(date.today())

        # Parse meals with nutrition data
        meals = {}
        for meal in mfp_day.meals:
            meal_name = meal.name.lower()
            meals[meal_name] = []
            for entry in meal.entries:
                meals[meal_name].append({
                    "name": entry.name,
                    "calories": _safe_float(entry.totals.get("calories")),
                    "protein": _safe_float(entry.totals.get("protein")),
                    "carbs": _safe_float(entry.totals.get("carbohydrates")),
                    "fat": _safe_float(entry.totals.get("fat")),
                })

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


def _save_food_cache(foods: list[dict]) -> None:
    """Save food database to JSON file."""
    try:
        with open(FOOD_DB_FILE, 'w') as f:
            json.dump(foods, f, indent=2)
        logger.info(f"Saved {len(foods)} foods to cache file")
    except Exception as e:
        logger.error(f"Error saving food cache: {e}")


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


# Mount static files (frontend)
import pathlib
static_dir = pathlib.Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

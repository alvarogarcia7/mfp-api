"""FastAPI server for MyFitnessPal web app."""

import asyncio
import uuid
from datetime import date
from typing import Annotated

from fastapi import FastAPI, HTTPException, Header, Depends, Body
from fastapi.staticfiles import StaticFiles

from vendor import mfp_client, diary
from mfp_auth import login_mfp

app = FastAPI()

# In-memory session storage: session_id -> CurlCffiClient
_sessions: dict[str, mfp_client.CurlCffiClient] = {}


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
    """Login with username/password, return session ID."""
    username = request.get("username")
    password = request.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username or password")

    try:
        cookies, mfp_username = await asyncio.to_thread(login_mfp, username, password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login error: {e}")

    # Create session and store client
    session_id = str(uuid.uuid4())
    try:
        client = mfp_client.build_client(cookies, username=mfp_username)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth failed: {e}")

    _sessions[session_id] = client
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


@app.post("/api/log")
async def log_food(request: dict = Body(...), session_id: str = Depends(get_session_id)):
    """Log food to diary."""
    client = get_client(session_id)

    food_id = request.get("food_id")
    weight_id = request.get("weight_id")
    quantity = request.get("quantity", 1.0)
    meal = request.get("meal", "breakfast")

    if not food_id or not weight_id:
        raise HTTPException(status_code=400, detail="Missing food_id or weight_id")

    def log_it():
        return diary.push_food(
            client,
            date.today(),
            meal,
            "",  # dummy query
            quantity=float(quantity),
            food_id=food_id,
            weight_id=weight_id,
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


# Mount static files (frontend)
import pathlib
static_dir = pathlib.Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

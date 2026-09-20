"""Repository for loading food diary data from cache."""

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


class DiaryRepository:
    """Load food diary entries from .diary_cache.json."""

    def __init__(self, cache_file: Path | None = None):
        """Initialize repository with cache file path.

        Args:
            cache_file: Path to .diary_cache.json. If None, uses default location.
        """
        if cache_file is None:
            cache_file = Path(__file__).parent.parent / ".diary_cache.json"
        self.cache_file = cache_file

    def load_entries_for_date(self, target_date: date) -> dict | None:
        """Load diary entries for a specific date.

        Args:
            target_date: Date to load entries for

        Returns:
            Dict with structure:
            {
                "date": "YYYY-MM-DD",
                "meals": {
                    "breakfast": [...],
                    "lunch": [...],
                    "dinner": [...],
                    "snacks": [...]
                },
                "totals": {...}
            }
            Or None if no entry found for this date.
        """
        cache = self._load_cache()
        if not cache:
            return None

        date_str = target_date.isoformat()
        for entry in cache:
            if entry.get("date") == date_str:
                return self._format_entry(entry)

        return None

    def _format_entry(self, entry: dict) -> dict:
        """Format raw cache entry into meal-organized structure.

        Args:
            entry: Raw entry from cache

        Returns:
            Formatted entry with meals organized by type
        """
        meals = {"breakfast": [], "lunch": [], "dinner": [], "snacks": []}

        # Group food entries by meal type
        for meal in entry.get("meals", []):
            meal_name = meal.get("name", "").lower()
            if meal_name not in meals:
                meal_name = "snacks"

            for food in meal.get("entries", []):
                food_data = {
                    "name": food.get("name", ""),
                    "quantity": food.get("quantity"),
                    "unit": food.get("unit", "g"),
                    "calories": food.get("totals", {}).get("calories", 0),
                    "protein": food.get("totals", {}).get("protein", 0.0),
                    "carbs": food.get("totals", {}).get("carbs", 0.0),
                    "fat": food.get("totals", {}).get("fat", 0.0),
                }
                meals[meal_name].append(food_data)

        return {
            "date": entry.get("date"),
            "meals": meals,
            "totals": entry.get("totals", {}),
            "metadata": entry.get("metadata", {}),
        }

    def _load_cache(self) -> list[dict] | None:
        """Load and parse cache file.

        Returns:
            List of diary entries, or None if file doesn't exist
        """
        if not self.cache_file.exists():
            logger.warning(f"Diary cache not found: {self.cache_file}")
            return None

        try:
            with open(self.cache_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading diary cache: {e}")
            return None

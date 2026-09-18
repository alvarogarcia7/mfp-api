"""Download and store MyFitnessPal Food Diary entries.

Fetches food diary data from MyFitnessPal API and persists to local storage.
"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Diary storage directory
DIARY_DATA_DIR = Path(__file__).parent.parent / "data" / "food_diary"
DIARY_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Diary index file tracking all diary entries
DIARY_INDEX_FILE = DIARY_DATA_DIR / ".diary_index.json"


class FoodDiarySyncManager:
    """Manages syncing and storing MyFitnessPal food diary entries."""

    def __init__(self, data_dir: Path = DIARY_DATA_DIR):
        """Initialize diary sync manager.

        Args:
            data_dir: Directory to store diary entries
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._load_index()

    def _load_index(self) -> None:
        """Load diary index from disk."""
        try:
            if DIARY_INDEX_FILE.exists():
                with open(DIARY_INDEX_FILE, 'r') as f:
                    self.index = json.load(f)
            else:
                self.index = {"entries": {}, "metadata": {}}
        except Exception as e:
            logger.warning(f"Failed to load diary index: {e}")
            self.index = {"entries": {}, "metadata": {}}

    def _save_index(self) -> None:
        """Save diary index to disk."""
        try:
            with open(DIARY_INDEX_FILE, 'w') as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save diary index: {e}")

    def add_diary_entry(self, entry_date: date, day_data: Any) -> str:
        """Add a food diary entry for a specific date.

        Args:
            entry_date: Date of the diary entry
            day_data: Day object from MFP API containing meals and entries

        Returns:
            Path to saved diary file
        """
        try:
            date_str = entry_date.isoformat()

            # Build diary entry structure
            meals_data = []
            for meal in day_data.meals:
                meal_data = {
                    "name": meal.name,
                    "entries": [],
                }

                # Collect all food entries for this meal
                for food_entry in meal.entries:
                    entry_item = {
                        "name": food_entry.name,
                        "quantity": getattr(food_entry, "quantity", None),
                        "unit": getattr(food_entry, "unit", None),
                        "totals": dict(food_entry.totals) if hasattr(food_entry.totals, "__iter__") else food_entry.totals,
                        "url": getattr(food_entry, "url", None),
                        "timestamp": datetime.now().isoformat(),
                    }
                    meal_data["entries"].append(entry_item)

                if meal_data["entries"]:
                    meals_data.append(meal_data)

            # Build complete diary entry
            diary_entry = {
                "date": date_str,
                "synced_at": datetime.now().isoformat(),
                "meals": meals_data,
                "metadata": {
                    "total_meals": len(meals_data),
                    "total_foods": sum(len(m["entries"]) for m in meals_data),
                }
            }

            # Save diary entry to file
            filename = f"diary_{date_str}.json"
            filepath = self.data_dir / filename

            with open(filepath, 'w') as f:
                json.dump(diary_entry, f, indent=2)

            # Extract metadata for logging and indexing
            total_foods: int = diary_entry["metadata"]["total_foods"]  # type: ignore

            # Update index
            self.index["entries"][date_str] = {
                "file": filename,
                "synced_at": datetime.now().isoformat(),
                "meals_count": len(meals_data),
                "foods_count": total_foods,
            }
            self._save_index()

            logger.info(f"Saved diary entry for {date_str} ({len(meals_data)} meals, {total_foods} foods)")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to add diary entry for {entry_date}: {e}")
            raise

    def get_diary_entry(self, entry_date: date) -> Optional[dict]:
        """Load a diary entry from disk.

        Args:
            entry_date: Date to load

        Returns:
            Diary entry dict or None if not found
        """
        try:
            date_str = entry_date.isoformat()
            if date_str not in self.index["entries"]:
                return None

            filename = self.index["entries"][date_str]["file"]
            filepath = self.data_dir / filename

            if not filepath.exists():
                return None

            with open(filepath, 'r') as f:
                return json.load(f)

        except Exception as e:
            logger.warning(f"Failed to load diary entry for {entry_date}: {e}")
            return None

    def get_diary_entries(self, start_date: date, end_date: date) -> list[dict]:
        """Load multiple diary entries for a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of diary entries
        """
        entries = []
        current = start_date

        while current <= end_date:
            entry = self.get_diary_entry(current)
            if entry:
                entries.append(entry)
            current += timedelta(days=1)

        return entries

    def list_dates(self) -> list[str]:
        """List all dates with diary entries.

        Returns:
            Sorted list of dates in YYYY-MM-DD format
        """
        return sorted(self.index["entries"].keys())

    def clear_diary(self) -> int:
        """Clear all diary entries.

        Returns:
            Number of files deleted
        """
        try:
            deleted = 0
            for entry_date in self.list_dates():
                filename = self.index["entries"][entry_date]["file"]
                filepath = self.data_dir / filename
                if filepath.exists():
                    filepath.unlink()
                    deleted += 1

            self.index = {"entries": {}, "metadata": {}}
            self._save_index()

            logger.info(f"Cleared {deleted} diary entries")
            return deleted

        except Exception as e:
            logger.error(f"Failed to clear diary: {e}")
            return 0

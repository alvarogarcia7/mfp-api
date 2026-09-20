#!/usr/bin/env python3
"""CLI script to parse raw MyFitnessPal diary data into processed format.

Reads raw diary JSON files, computes daily totals, validates against schema,
and saves to cache.

Usage:
    python cli_parse_diary.py --merge
    python cli_parse_diary.py --replace
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from jsonschema import validate, ValidationError

from . import library

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BACKEND_DIR = Path(__file__).parent.parent
RAW_DATA_DIR = BACKEND_DIR / "data" / "raw_diary_data"
DIARY_CACHE_FILE = BACKEND_DIR / ".diary_cache.json"
BACKUP_DIR = BACKEND_DIR / ".backups"
BACKUP_DIR.mkdir(exist_ok=True)

# Schema for parsed diary
DIARY_SCHEMA_FILE = BACKEND_DIR / "diary_schema.json"


def load_raw_diary_files(specific_file: str | None = None) -> dict[str, dict]:
    """Load all raw diary JSON files.

    Args:
        specific_file: If provided, load only this file

    Returns:
        Dict mapping filename -> raw data
    """
    raw_files = {}

    if specific_file:
        filepath = RAW_DATA_DIR / specific_file
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            sys.exit(1)
        files_to_process = [filepath]
    else:
        if not RAW_DATA_DIR.exists():
            logger.warning(f"Raw data directory not found: {RAW_DATA_DIR}")
            return {}
        files_to_process = list(RAW_DATA_DIR.glob("diary_*.json"))

    if not files_to_process:
        logger.warning("No raw diary files found")
        return {}

    for filepath in sorted(files_to_process):
        try:
            logger.info(f"Loading {filepath.name}")
            with open(filepath, 'r') as f:
                data = json.load(f)
            raw_files[filepath.name] = data

            # Count entries
            entries = data.get("diary_entries", [])
            logger.debug(f"  Loaded {len(entries)} diary entries")

        except Exception as e:
            logger.warning(f"Failed to load {filepath.name}: {e}")

    return raw_files


def compute_totals(food_list: list[dict]) -> dict:
    """Compute nutritional totals from a list of food entries.

    Args:
        food_list: List of food dicts with 'calories', 'protein', etc.

    Returns:
        Dict with totals
    """
    totals = {
        "calories": 0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
    }

    for food in food_list:
        totals["calories"] += library.safe_int(food.get("calories", 0))
        totals["protein"] += library.safe_float(food.get("protein", 0.0))
        totals["carbs"] += library.safe_float(food.get("carbs", 0.0))
        totals["fat"] += library.safe_float(food.get("fat", 0.0))

    return totals


def parse_and_compute_totals(raw_files: dict) -> list[dict]:
    """Parse raw diary entries and compute totals.

    Args:
        raw_files: Dict of raw data from load_raw_diary_files()

    Returns:
        List of parsed diary entries with computed totals
    """
    parsed_entries = []

    for filename, data in raw_files.items():
        logger.info(f"Processing {filename}")
        diary_entries = data.get("diary_entries", [])

        for entry in diary_entries:
            try:
                parsed_entry = {
                    "date": entry.get("date", ""),
                    "synced_at": entry.get("synced_at", datetime.now().isoformat()),
                    "meals": [],
                    "totals": {
                        "calories": 0,
                        "protein": 0.0,
                        "carbs": 0.0,
                        "fat": 0.0,
                    },
                    "metadata": {
                        "total_meals": 0,
                        "total_foods": 0,
                    },
                }

                # Process each meal
                meals = entry.get("meals", [])
                total_foods = 0

                for meal in meals:
                    meal_entries = meal.get("entries", [])
                    if not meal_entries:
                        continue

                    # Compute meal subtotal
                    meal_subtotal = compute_totals(meal_entries)

                    # Extract simplified food entries
                    foods = []
                    for food in meal_entries:
                        foods.append({
                            "name": food.get("name", ""),
                            "quantity": library.safe_float(food.get("quantity")),
                            "unit": food.get("unit", ""),
                            "totals": {
                                "calories": library.safe_int(food.get("calories", 0)),
                                "protein": library.safe_float(food.get("protein", 0.0)),
                                "carbs": library.safe_float(food.get("carbs", 0.0)),
                                "fat": library.safe_float(food.get("fat", 0.0)),
                            }
                        })

                    # Add meal with computed subtotal
                    parsed_entry["meals"].append({
                        "name": meal.get("name", ""),
                        "entries": foods,
                    })

                    # Update daily totals
                    parsed_entry["totals"]["calories"] += meal_subtotal["calories"]
                    parsed_entry["totals"]["protein"] += meal_subtotal["protein"]
                    parsed_entry["totals"]["carbs"] += meal_subtotal["carbs"]
                    parsed_entry["totals"]["fat"] += meal_subtotal["fat"]

                    total_foods += len(meal_entries)

                # Update metadata
                parsed_entry["metadata"]["total_meals"] = len([m for m in meals if m.get("entries")])
                parsed_entry["metadata"]["total_foods"] = total_foods

                parsed_entries.append(parsed_entry)

            except Exception as e:
                logger.error(f"Error parsing diary entry for {entry.get('date')}: {e}", exc_info=True)

    return parsed_entries


def load_existing_cache() -> list[dict]:
    """Load existing diary cache if it exists."""
    if not DIARY_CACHE_FILE.exists():
        return []

    try:
        with open(DIARY_CACHE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load existing cache: {e}")
        return []


def merge_diary_entries(new_entries: list[dict], existing_entries: list[dict]) -> list[dict]:
    """Merge new diary entries with existing cache, avoiding duplicates by date.

    Args:
        new_entries: Newly parsed entries
        existing_entries: Existing entries in cache

    Returns:
        Merged list of unique entries
    """
    entries_map = {}

    # Add existing entries first
    for entry in existing_entries:
        date = entry.get("date")
        if date:
            entries_map[date] = entry

    # Add new entries (overwrite if exists)
    for entry in new_entries:
        date = entry.get("date")
        if date:
            entries_map[date] = entry

    logger.info(f"Merged: {len(existing_entries)} existing + {len(new_entries)} new = {len(entries_map)} total")
    return [entries_map[date] for date in sorted(entries_map.keys())]


def backup_diary_cache() -> str | None:
    """Create a backup of the existing diary cache.

    Returns:
        Path to backup file, or None if no cache exists
    """
    if not DIARY_CACHE_FILE.exists():
        return None

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"diary_cache_{timestamp}.json"

        with open(DIARY_CACHE_FILE, 'r') as f:
            data = json.load(f)

        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"📦 Backed up existing cache to {backup_file.name}")
        return str(backup_file)

    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return None


def save_diary_cache(entries: list[dict], replace_mode: bool = False, force_replace: bool = False) -> None:
    """Save diary cache to disk.

    Args:
        entries: List of diary entry objects to save
        replace_mode: If True, will replace existing cache (requires confirmation)
        force_replace: If True, replace without creating backup
    """
    DIARY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Handle replace mode
    if replace_mode:
        if DIARY_CACHE_FILE.exists():
            if force_replace:
                logger.warning("⚠️  Replacing existing cache (no backup created)")
            else:
                logger.info("Creating backup of existing cache before replace...")
                backup_diary_cache()

    with open(DIARY_CACHE_FILE, 'w') as f:
        json.dump(entries, f, indent=2)

    logger.info(f"✅ Saved {len(entries)} diary entries to {DIARY_CACHE_FILE}")


def summarize_diary(entries: list[dict]) -> None:
    """Print a summary of diary entries grouped by date with totals.

    Args:
        entries: List of parsed diary entries
    """
    if not entries:
        logger.info("No diary entries to summarize")
        return

    logger.info("=" * 60)
    logger.info("📊 Diary Summary")
    logger.info("=" * 60)

    total_calories = 0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0

    for entry in sorted(entries, key=lambda x: x.get("date", "")):
        date = entry.get("date", "Unknown")
        totals = entry.get("totals", {})
        metadata = entry.get("metadata", {})

        calories = library.safe_int(totals.get("calories", 0))
        protein = library.safe_float(totals.get("protein", 0.0))
        carbs = library.safe_float(totals.get("carbs", 0.0))
        fat = library.safe_float(totals.get("fat", 0.0))

        total_calories += calories
        total_protein += protein
        total_carbs += carbs
        total_fat += fat

        meals = metadata.get("total_meals", 0)
        foods = metadata.get("total_foods", 0)

        logger.info(f"\n📅 {date}")
        logger.info(f"  Meals: {meals}, Foods: {foods}")
        logger.info(f"  Calories: {calories:,} | Protein: {protein:.1f}g | Carbs: {carbs:.1f}g | Fat: {fat:.1f}g")

    logger.info("-" * 60)
    logger.info(f"Total: {len(entries)} days | Calories: {total_calories:,} | Protein: {total_protein:.1f}g | Carbs: {total_carbs:.1f}g | Fat: {total_fat:.1f}g")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Parse raw MyFitnessPal diary data into processed format"
    )

    merge_group = parser.add_mutually_exclusive_group()
    merge_group.add_argument(
        "--merge",
        action="store_true",
        default=True,
        help="Merge with existing cache (default, keeps existing entries)"
    )
    merge_group.add_argument(
        "--replace",
        action="store_true",
        help="Replace existing cache (creates backup file)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Use with --replace to skip backup and force overwrite (destructive!)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.force and not args.replace:
        logger.error("❌ --force can only be used with --replace")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("MyFitnessPal Diary Parser")
    logger.info("=" * 60)

    # Load raw files
    logger.info(f"Looking for raw diary data in {RAW_DATA_DIR}")
    raw_files = load_raw_diary_files()

    if not raw_files:
        logger.error("No raw diary data to process")
        sys.exit(1)

    # Parse and compute totals
    logger.info(f"Processing {len(raw_files)} file(s)")
    new_entries = parse_and_compute_totals(raw_files)
    logger.info(f"Parsed {len(new_entries)} diary entries")

    # Validate against schema
    schema = library.load_schema(DIARY_SCHEMA_FILE)
    valid_count, invalid_count = library.validate_data(new_entries, schema, "diary entry")

    if invalid_count > 0:
        logger.warning(f"⚠️  {invalid_count} entries failed validation (marked as invalid)")

    # Merge or replace
    if args.replace:
        logger.info("Replace mode: will overwrite existing cache")
        final_entries = new_entries
        save_diary_cache(final_entries, replace_mode=True, force_replace=args.force)
    else:
        logger.info("Merge mode: combining with existing cache (default)")
        existing_entries = load_existing_cache()
        final_entries = merge_diary_entries(new_entries, existing_entries)
        save_diary_cache(final_entries, replace_mode=False)

    logger.info("=" * 60)
    logger.info(f"✅ Diary cache updated: {len(final_entries)} entries")
    logger.info("=" * 60)

    # Print summary
    summarize_diary(final_entries)


if __name__ == "__main__":
    main()

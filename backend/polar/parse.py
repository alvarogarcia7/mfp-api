#!/usr/bin/env python3
"""CLI script to parse raw Polar Flow calendar events data into Exercise Diary JSON.

Reads raw JSON files from data/raw_polar_data/, parses events, and saves
to the exercise database.

Usage:
    python cli_parse_polar_data.py                    # Parse all raw files
    python cli_parse_polar_data.py --file <filename>  # Parse specific file
    python cli_parse_polar_data.py --merge            # Merge with existing cache
    python cli_parse_polar_data.py --replace          # Replace existing cache (default)
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BACKEND_DIR = Path(__file__).parent
RAW_DATA_DIR = BACKEND_DIR.parent / "data" / "raw_polar_data"
EXERCISE_DB_FILE = BACKEND_DIR / ".exercise_cache.json"
BACKUP_DIR = BACKEND_DIR / ".backups"
BACKUP_DIR.mkdir(exist_ok=True)


def load_raw_polar_files(specific_file: str | None = None) -> dict[str, dict]:
    """Load all raw Polar Flow calendar JSON files.

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
        files_to_process = list(RAW_DATA_DIR.glob("polar_calendar_*.json"))

    if not files_to_process:
        logger.warning("No raw Polar Flow data files found")
        return {}

    for filepath in sorted(files_to_process):
        try:
            logger.info(f"Loading {filepath.name}")
            with open(filepath, 'r') as f:
                data = json.load(f)
            raw_files[filepath.name] = data

            # Count events
            raw_response = data.get("raw_response", {})
            if isinstance(raw_response, list):
                event_count = len(raw_response)
            else:
                event_count = len(raw_response.get("events", []))
            logger.debug(f"  Loaded {event_count} events")

        except Exception as e:
            logger.warning(f"Failed to load {filepath.name}: {e}")

    return raw_files


def parse_and_deduplicate(raw_files: dict) -> list[dict]:
    """Parse raw Polar Flow calendar events and deduplicate.

    Args:
        raw_files: Dict of raw data from load_raw_polar_files()

    Returns:
        List of unique exercises
    """
    exercises_map = {}  # id -> exercise_data

    for filename, data in raw_files.items():
        logger.info(f"Processing {filename}")
        raw_response = data.get("raw_response", {})

        # Handle both list and dict responses
        if isinstance(raw_response, list):
            events = raw_response
        else:
            events = raw_response.get("events", [])

        for event in events:
            if not isinstance(event, dict):
                logger.debug(f"Skipping non-dict event: {type(event)}")
                continue

            # Extract event ID for deduplication (use listItemId from Polar API)
            event_id = event.get("listItemId") or event.get("id")
            if not event_id:
                logger.debug("Skipping event without ID")
                continue

            # Parse exercise data
            exercise = parse_event(event)
            if exercise:
                # Store only if not already seen (keep first occurrence)
                if event_id not in exercises_map:
                    exercises_map[event_id] = exercise

    return list(exercises_map.values())


def parse_event(event: dict) -> dict | None:
    """Parse a Polar Flow calendar event into exercise format.

    Args:
        event: Raw event dict from API

    Returns:
        Parsed exercise dict or None if invalid
    """
    try:
        # Extract event fields from Polar API response
        event_id = event.get("listItemId") or event.get("id")
        # Use sport name if available, otherwise fall back to type
        sport_info = event.get("sport")
        if isinstance(sport_info, dict):
            event_type = sport_info.get("name", event.get("type", "Unknown"))
        else:
            event_type = sport_info or event.get("type") or event.get("eventType", "Unknown")
        duration_ms = event.get("duration", 0)  # In milliseconds
        calories = event.get("calories", 0)
        datetime_str = event.get("datetime", "")  # Format: "2026-08-20T21:09:52.237Z"
        distance = event.get("distance")
        title = event.get("title", "")

        if not duration_ms or not calories:
            logger.debug(f"Skipping event: missing duration or calories")
            return None

        # Convert milliseconds to minutes
        duration_minutes = int(duration_ms / 1000 / 60)

        # Extract date from datetime (ISO format: YYYY-MM-DDTHH:MM:SS.xxxZ)
        try:
            activity_date = datetime_str.split("T")[0] if "T" in datetime_str else ""
        except (IndexError, AttributeError):
            activity_date = ""

        if not activity_date:
            logger.warning(f"Event {event_id}: missing activity date")
            return None

        exercise = {
            "id": event_id,
            "sport_name": event_type,
            "duration_minutes": duration_minutes,
            "calories": int(calories),
            "date": activity_date,
            "start_time": datetime_str,
            "name": f"Polar Flow - {event_type}",
            "title": title,
        }

        # Add optional fields
        if distance is not None:
            exercise["distance"] = distance

        # Add other available fields
        for key in ["recoveryTime", "trainingLoadHtml", "trainingLoadProHtml", "periodDataUuid"]:
            if key in event:
                exercise[key] = event[key]

        return exercise

    except Exception as e:
        logger.error(f"Error parsing event {event.get('id')}: {e}", exc_info=True)
        return None


def load_existing_cache() -> list[dict]:
    """Load existing exercise cache if it exists."""
    if not EXERCISE_DB_FILE.exists():
        return []

    try:
        with open(EXERCISE_DB_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load existing cache: {e}")
        return []


def merge_exercises(new_exercises: list[dict], existing_exercises: list[dict]) -> list[dict]:
    """Merge new exercises with existing cache, avoiding duplicates by ID.

    Args:
        new_exercises: Newly parsed exercises
        existing_exercises: Existing exercises in cache

    Returns:
        Merged list of unique exercises
    """
    exercises_map = {}

    # Add existing exercises first
    for exercise in existing_exercises:
        exercise_id = exercise.get("id")
        if exercise_id:
            exercises_map[exercise_id] = exercise

    # Add new exercises (overwrite if exists)
    for exercise in new_exercises:
        exercise_id = exercise.get("id")
        if exercise_id:
            exercises_map[exercise_id] = exercise

    logger.info(f"Merged: {len(existing_exercises)} existing + {len(new_exercises)} new = {len(exercises_map)} total")
    return list(exercises_map.values())


def backup_exercise_cache() -> str | None:
    """Create a backup of the existing exercise cache.

    Returns:
        Path to backup file, or None if no cache exists
    """
    if not EXERCISE_DB_FILE.exists():
        return None

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"exercise_cache_{timestamp}.json"

        # Copy existing file to backup
        with open(EXERCISE_DB_FILE, 'r') as f:
            data = json.load(f)

        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"📦 Backed up existing cache to {backup_file.name}")
        return str(backup_file)

    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return None


def save_exercise_cache(exercises: list[dict], replace_mode: bool = False, force_replace: bool = False) -> None:
    """Save exercise cache to disk.

    Args:
        exercises: List of exercise objects to save
        replace_mode: If True, will replace existing cache (requires confirmation)
        force_replace: If True, replace without creating backup
    """
    # Ensure directory exists
    EXERCISE_DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Handle replace mode
    if replace_mode:
        if EXERCISE_DB_FILE.exists():
            if force_replace:
                logger.warning("⚠️  Replacing existing cache (no backup created)")
            else:
                logger.info("Creating backup of existing cache before replace...")
                backup_exercise_cache()

    with open(EXERCISE_DB_FILE, 'w') as f:
        json.dump(exercises, f, indent=2)

    logger.info(f"✅ Saved {len(exercises)} exercises to {EXERCISE_DB_FILE}")


def summarize_exercises(exercises: list[dict]) -> None:
    """Print a summary of exercises grouped by date and activity type.

    Args:
        exercises: List of parsed exercises
    """
    if not exercises:
        logger.info("No exercises to summarize")
        return

    # Group by date, then by sport_name
    daily_summary = {}
    for exercise in exercises:
        date_str = exercise.get("date", "Unknown")
        sport = exercise.get("sport_name", "Unknown")
        calories = exercise.get("calories", 0)

        if date_str not in daily_summary:
            daily_summary[date_str] = {}

        if sport not in daily_summary[date_str]:
            daily_summary[date_str][sport] = {"count": 0, "calories": 0}

        daily_summary[date_str][sport]["count"] += 1
        daily_summary[date_str][sport]["calories"] += calories

    # Print summary
    logger.info("=" * 60)
    logger.info("📊 Exercise Summary")
    logger.info("=" * 60)

    total_calories = 0
    total_activities = 0

    # Sort by date
    for date_str in sorted(daily_summary.keys()):
        day_total = 0
        activities_per_day = 0

        logger.info(f"\n📅 {date_str}")
        # Sort sports alphabetically within each day
        for sport in sorted(daily_summary[date_str].keys()):
            count = daily_summary[date_str][sport]["count"]
            calories = daily_summary[date_str][sport]["calories"]
            day_total += calories
            activities_per_day += count
            total_calories += calories
            total_activities += count
            logger.info(f"  {count}x {sport} (subtotal={calories:,} kcal)")

        logger.info(f"  → Day total: {activities_per_day} activities ({day_total:,} kcal)")

    logger.info("-" * 60)
    logger.info(f"Total: {total_activities} activities ({total_calories:,} kcal)")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Parse raw Polar Flow calendar events into Exercise Diary JSON"
    )

    parser.add_argument(
        "--file",
        help="Parse specific raw data file (filename only, not full path)"
    )

    merge_group = parser.add_mutually_exclusive_group()
    merge_group.add_argument(
        "--merge",
        action="store_true",
        default=True,
        help="Merge with existing cache (default, keeps existing exercises)"
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
    logger.info("Polar Flow Data Parser")
    logger.info("=" * 60)

    # Load raw files
    logger.info(f"Looking for raw Polar Flow data in {RAW_DATA_DIR}")
    raw_files = load_raw_polar_files(args.file)

    if not raw_files:
        logger.error("No raw Polar Flow data to process")
        sys.exit(1)

    # Parse and deduplicate
    logger.info(f"Processing {len(raw_files)} file(s)")
    new_exercises = parse_and_deduplicate(raw_files)
    logger.info(f"Parsed {len(new_exercises)} unique exercises")

    # Merge or replace
    if args.replace:
        logger.info("Replace mode: will overwrite existing cache")
        final_exercises = new_exercises
        save_exercise_cache(final_exercises, replace_mode=True, force_replace=args.force)
    else:
        logger.info("Merge mode: combining with existing cache (default)")
        existing_exercises = load_existing_cache()
        final_exercises = merge_exercises(new_exercises, existing_exercises)
        save_exercise_cache(final_exercises, replace_mode=False)

    logger.info("=" * 60)
    logger.info(f"✅ Exercise database updated: {len(final_exercises)} exercises")
    logger.info("=" * 60)

    # Print activity summary
    summarize_exercises(final_exercises)


if __name__ == "__main__":
    main()

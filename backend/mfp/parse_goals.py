#!/usr/bin/env python3
"""CLI script to parse user goals into user profile database.

Reads raw goals JSON files, validates against schema,
and saves to user profile cache.

Usage:
    python -m backend.mfp.parse_goals
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
RAW_DATA_DIR = BACKEND_DIR / "data" / "raw_goals_data"
USER_DATA_DIR = BACKEND_DIR / "data" / "user"
USER_PROFILE_FILE = USER_DATA_DIR / "profile.json"
USER_PROFILE_SCHEMA_FILE = BACKEND_DIR / "user_profile_schema.json"


def load_raw_goals_files() -> dict:
    """Load all raw goals JSON files.

    Returns:
        Dict mapping filename -> raw data
    """
    raw_files = {}

    if not RAW_DATA_DIR.exists():
        logger.warning(f"Raw data directory not found: {RAW_DATA_DIR}")
        return {}

    files_to_process = list(RAW_DATA_DIR.glob("user_goals_*.json"))

    if not files_to_process:
        logger.warning("No raw goals files found")
        return {}

    # Sort by modification time, get the latest
    files_to_process.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    latest_file = files_to_process[0]

    try:
        logger.info(f"Loading {latest_file.name}")
        with open(latest_file, 'r') as f:
            data = json.load(f)
        raw_files[latest_file.name] = data
    except Exception as e:
        logger.warning(f"Failed to load {latest_file.name}: {e}")

    return raw_files


def parse_user_goals(raw_files: dict) -> dict | None:
    """Parse raw user goals data.

    Args:
        raw_files: Dict of raw data from load_raw_goals_files()

    Returns:
        Parsed user profile dict, or None if no data
    """
    if not raw_files:
        return None

    filename, data = list(raw_files.items())[0]
    logger.info(f"Processing {filename}")

    try:
        parsed_profile = {
            "username": data.get("username", "unknown"),
            "updated_at": datetime.now().isoformat(),
            "fetched_at": data.get("fetched_at", datetime.now().isoformat()),
            "goals": data.get("goals", {}),
            "preferences": data.get("preferences", {}),
            "profile": data.get("profile", {}),
        }

        return parsed_profile

    except Exception as e:
        logger.error(f"Error parsing user goals: {e}", exc_info=True)
        return None


def load_existing_profile() -> dict | None:
    """Load existing user profile if it exists."""
    if not USER_PROFILE_FILE.exists():
        return None

    try:
        with open(USER_PROFILE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load existing profile: {e}")
        return None


def save_user_profile(profile: dict) -> None:
    """Save user profile to disk.

    Args:
        profile: User profile dict to save
    """
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Validate against schema
    schema = library.load_schema(USER_PROFILE_SCHEMA_FILE)
    try:
        validate(instance=profile, schema=schema)
        logger.info("✅ Profile validation passed")
    except ValidationError as e:
        logger.warning(f"⚠️  Profile validation warning: {e.message}")

    with open(USER_PROFILE_FILE, 'w') as f:
        json.dump(profile, f, indent=2)

    logger.info(f"✅ Saved user profile to {USER_PROFILE_FILE}")


def main():
    parser = argparse.ArgumentParser(
        description="Parse user goals into profile database"
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("MyFitnessPal User Goals Parser")
    logger.info("=" * 60)

    # Load raw files
    logger.info(f"Looking for raw goals data in {RAW_DATA_DIR}")
    raw_files = load_raw_goals_files()

    if not raw_files:
        logger.error("No raw goals data to process")
        sys.exit(1)

    # Parse goals
    logger.info(f"Processing {len(raw_files)} file(s)")
    parsed_profile = parse_user_goals(raw_files)

    if not parsed_profile:
        logger.error("Failed to parse goals")
        sys.exit(1)

    # Save profile
    save_user_profile(parsed_profile)

    # Print summary
    logger.info("=" * 60)
    logger.info("📊 User Profile Summary")
    logger.info("=" * 60)
    logger.info(f"Username: {parsed_profile.get('username')}")
    logger.info(f"")
    logger.info(f"Daily Goals:")

    goals = parsed_profile.get("goals", {})
    for goal_name, goal_data in goals.items():
        if isinstance(goal_data, dict) and "value" in goal_data:
            unit = goal_data.get("unit", "")
            value = goal_data.get("value", 0)
            logger.info(f"  {goal_name.replace('_', ' ').title()}: {value} {unit}")

    logger.info("=" * 60)


if __name__ == "__main__":
    main()

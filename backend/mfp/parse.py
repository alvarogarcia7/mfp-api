#!/usr/bin/env python3
"""CLI script to parse raw food data into the Food Database JSON.

Reads raw JSON files from data/raw_food_data/, deduplicates, validates, and saves
to the .food_cache.json database file.

Usage:
    python cli_parse_food_data.py                    # Parse all raw files
    python cli_parse_food_data.py --file <filename>  # Parse specific file
    python cli_parse_food_data.py --merge            # Merge with existing cache
    python cli_parse_food_data.py --replace          # Replace existing cache (default)
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from jsonschema import validate, ValidationError

from . import unit_conversion

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BACKEND_DIR = Path(__file__).parent.parent
RAW_DATA_DIR = BACKEND_DIR / "data" / "raw_food_data"
FOOD_CACHE_FILE = BACKEND_DIR / ".food_cache.json"
MFP_FOOD_SCHEMA_FILE = BACKEND_DIR / "mfp_food_schema.json"
FOOD_SCHEMA_FILE = BACKEND_DIR / "food_schema.json"
BACKUP_DIR = BACKEND_DIR / ".backups"
BACKUP_DIR.mkdir(exist_ok=True)


def load_mfp_schema() -> dict:
    """Load MFP Food Fact schema for validating raw input data."""
    try:
        with open(MFP_FOOD_SCHEMA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load MFP food schema: {e}")
        sys.exit(1)


def load_food_schema() -> dict:
    """Load domain Food Fact schema for validating output data."""
    try:
        with open(FOOD_SCHEMA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load food schema: {e}")
        sys.exit(1)


def load_raw_food_files(specific_file: str | None = None, mfp_schema: dict | None = None) -> dict:
    """Load all raw food JSON files and validate against MFP schema.

    Args:
        specific_file: If provided, load only this file
        mfp_schema: MFP Food Fact schema for validating input data

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
        files_to_process = list(RAW_DATA_DIR.glob("food_data_*.json"))

    if not files_to_process:
        logger.warning("No raw food data files found")
        return {}

    for filepath in sorted(files_to_process):
        try:
            logger.info(f"Loading {filepath.name}")
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Validate raw foods against MFP schema
            if mfp_schema:
                foods = data.get('foods', [])
                for idx, food in enumerate(foods):
                    try:
                        validate(instance=food, schema=mfp_schema)
                    except ValidationError as e:
                        logger.warning(f"Food {idx} in {filepath.name} failed MFP validation: {food.get('name')} - {e.message}")

            raw_files[filepath.name] = data
            logger.debug(f"  Loaded {len(data.get('foods', []))} foods")
        except Exception as e:
            logger.warning(f"Failed to load {filepath.name}: {e}")

    return raw_files


def parse_and_deduplicate(raw_files: dict) -> list[dict]:
    """Parse raw food data and deduplicate.

    Args:
        raw_files: Dict of raw data from load_raw_food_files()

    Returns:
        List of unique foods
    """
    foods_map = {}  # name -> food_data

    for filename, data in raw_files.items():
        logger.info(f"Processing {filename}")
        foods = data.get("foods", [])

        for food in foods:
            name = food.get("name")
            if not name:
                logger.debug("Skipping food without name")
                continue

            # Skip foods marked as invalid during fetch
            if food.get("valid") is False:
                logger.debug(f"Skipping invalid food from fetch: {name}")
                continue

            # Store only first occurrence of each food (by name)
            if name not in foods_map:
                # Convert raw measurement to standardized grams
                raw_measurement = food.get("measurement", {})
                raw_value = raw_measurement.get("value")
                raw_unit = raw_measurement.get("unit")

                if raw_value is not None and raw_unit:
                    measurement = unit_conversion.standardize_measurement(raw_value, raw_unit)
                else:
                    # Default if measurement is missing
                    measurement = {"unit": "g", "value": 100.0}

                foods_map[name] = {
                    "name": name,
                    "measurement": measurement,
                    "calories": food.get("calories", 0),
                    "protein": food.get("protein", 0),
                    "carbs": food.get("carbohydrates", 0),
                    "fat": food.get("fat", 0),
                    "fiber": food.get("fiber", 0),
                    "sugar": food.get("sugar", 0),
                    "sodium": food.get("sodium", 0),
                    "cholesterol": food.get("cholesterol", 0),
                    "saturated_fat": food.get("saturated_fat", 0),
                    "potassium": food.get("potassium", 0),
                }

    return list(foods_map.values())


def validate_foods(foods: list[dict], schema: dict) -> int:
    """Validate foods against schema.

    Args:
        foods: List of food objects
        schema: JSON Schema for validation

    Returns:
        Number of valid foods
    """
    valid_count = 0
    invalid_count = 0

    for idx, food in enumerate(foods):
        try:
            validate(instance=food, schema=schema)
            valid_count += 1
        except ValidationError as e:
            invalid_count += 1
            logger.warning(f"Food {idx} validation failed: {food.get('name')} - {e.message}")

    logger.info(f"Validation results: {valid_count} valid, {invalid_count} invalid")
    return valid_count


def load_existing_cache() -> list[dict]:
    """Load existing food cache if it exists."""
    if not FOOD_CACHE_FILE.exists():
        return []

    try:
        with open(FOOD_CACHE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load existing cache: {e}")
        return []


def merge_foods(new_foods: list[dict], existing_foods: list[dict]) -> list[dict]:
    """Merge new foods with existing cache, avoiding duplicates.

    Args:
        new_foods: Newly parsed foods
        existing_foods: Existing foods in cache

    Returns:
        Merged list of unique foods
    """
    foods_map = {}

    # Add existing foods first
    for food in existing_foods:
        name = food.get("name")
        if name:
            foods_map[name] = food

    # Add new foods (overwrite if exists)
    for food in new_foods:
        name = food.get("name")
        if name:
            foods_map[name] = food

    logger.info(f"Merged: {len(existing_foods)} existing + {len(new_foods)} new = {len(foods_map)} total")
    return list(foods_map.values())


def backup_food_cache() -> str | None:
    """Create a backup of the existing food cache.

    Returns:
        Path to backup file, or None if no cache exists
    """
    if not FOOD_CACHE_FILE.exists():
        return None

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"food_cache_{timestamp}.json"

        # Copy existing file to backup
        with open(FOOD_CACHE_FILE, 'r') as f:
            data = json.load(f)

        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"📦 Backed up existing cache to {backup_file.name}")
        return str(backup_file)

    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return None


def save_food_cache(foods: list[dict], replace_mode: bool = False, force_replace: bool = False) -> None:
    """Save food cache to disk.

    Args:
        foods: List of food objects to save
        replace_mode: If True, will replace existing cache (requires confirmation)
        force_replace: If True, replace without creating backup
    """
    # Ensure directory exists
    FOOD_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Handle replace mode
    if replace_mode:
        if FOOD_CACHE_FILE.exists():
            if force_replace:
                logger.warning("⚠️  Replacing existing cache (no backup created)")
            else:
                logger.info("Creating backup of existing cache before replace...")
                backup_food_cache()

    with open(FOOD_CACHE_FILE, 'w') as f:
        json.dump(foods, f, indent=2)

    logger.info(f"✅ Saved {len(foods)} foods to {FOOD_CACHE_FILE}")


def main():
    parser = argparse.ArgumentParser(
        description="Parse raw food data into the Food Database JSON"
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
        help="Merge with existing cache (default, keeps existing foods)"
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
    logger.info("Food Data Parser")
    logger.info("=" * 60)

    # Load schemas
    mfp_schema = load_mfp_schema()
    domain_schema = load_food_schema()

    # Load raw files with MFP validation
    logger.info(f"Looking for raw food data in {RAW_DATA_DIR}")
    raw_files = load_raw_food_files(args.file, mfp_schema)

    if not raw_files:
        logger.error("No raw food data to process")
        sys.exit(1)

    # Parse and deduplicate
    logger.info(f"Processing {len(raw_files)} file(s)")
    new_foods = parse_and_deduplicate(raw_files)
    logger.info(f"Parsed {len(new_foods)} unique foods")

    # Validate parsed output against domain schema
    validate_foods(new_foods, domain_schema)

    # Merge or replace
    if args.replace:
        logger.info("Replace mode: will overwrite existing cache")
        final_foods = new_foods
        save_food_cache(final_foods, replace_mode=True, force_replace=args.force)
    else:
        logger.info("Merge mode: combining with existing cache (default)")
        existing_foods = load_existing_cache()
        final_foods = merge_foods(new_foods, existing_foods)
        save_food_cache(final_foods, replace_mode=False)

    logger.info("=" * 60)
    logger.info(f"✅ Food database updated: {len(final_foods)} foods")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""CLI script to download raw food data from MyFitnessPal API.

Downloads diary entries for a date range and saves raw JSON to disk.
Useful for building and updating the food database.

Usage:
    python cli_fetch_food_data.py --username user@example.com --password secret --today
    python cli_fetch_food_data.py --username user@example.com --password secret --last-two-weeks
    python cli_fetch_food_data.py --username user@example.com --password secret --last-month
    python cli_fetch_food_data.py --username user@example.com --password secret --range-start 2026-09-01 --range-end 2026-09-15
    python cli_fetch_food_data.py --cookie <session_token> --last-month
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from jsonschema import validate, ValidationError

from ..mfp_auth import login_mfp_password, login_mfp_cookie
from ..vendor import mfp_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Raw data directory
RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw_food_data"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# MFP Food Fact schema for validating raw API responses
MFP_FOOD_SCHEMA_FILE = Path(__file__).parent.parent / "mfp_food_schema.json"


def parse_date_range(args) -> tuple[date, date]:
    """Parse date range from CLI arguments."""
    today = date.today()

    if args.today:
        return today, today
    elif args.last_two_weeks:
        start = today - timedelta(days=14)
        return start, today
    elif args.last_month:
        start = today - timedelta(days=30)
        return start, today
    elif args.range_start and args.range_end:
        try:
            start = date.fromisoformat(args.range_start)
            end = date.fromisoformat(args.range_end)
            if start > end:
                logger.error("range-start must be before range-end")
                sys.exit(1)
            return start, end
        except ValueError as e:
            logger.error(f"Invalid date format: {e}. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        logger.error("Must specify one of: --today, --last-two-weeks, --last-month, or --range-start/--range-end")
        sys.exit(1)


def fetch_and_save_food_data(client, start_date: date, end_date: date) -> str:
    """Fetch food data from MFP for date range and save to disk.

    Args:
        client: Authenticated MFP client
        start_date: Start date
        end_date: End date

    Returns:
        Path to saved JSON file
    """
    logger.info(f"Fetching food data from {start_date} to {end_date}")

    all_foods = {}  # {name -> food_data}

    current = start_date
    while current <= end_date:
        try:
            logger.debug(f"Fetching diary for {current}")
            mfp_day = client.get_date(current)

            for meal in mfp_day.meals:
                for entry in meal.entries:
                    name = entry.name

                    # Store first occurrence of each food (by name)
                    if name not in all_foods:
                        # Get measurement: prefer "1 gram" format, fallback to quantity + unit
                        measurement = _get_measurement(entry)

                        all_foods[name] = {
                            "name": name,
                            "measurement": measurement,
                            "calories": _safe_float(entry.totals.get("calories")),
                            "protein": _safe_float(entry.totals.get("protein")),
                            "carbs": _safe_float(entry.totals.get("carbohydrates")),
                            "fat": _safe_float(entry.totals.get("fat")),
                            "fiber": _safe_float(entry.totals.get("fiber")),
                            "sugar": _safe_float(entry.totals.get("sugar")),
                            "sodium": _safe_float(entry.totals.get("sodium")),
                            "cholesterol": _safe_float(entry.totals.get("cholesterol")),
                            "saturated_fat": _safe_float(entry.totals.get("saturated_fat")),
                            "potassium": _safe_float(entry.totals.get("potassium")),
                        }

        except Exception as e:
            logger.warning(f"Error fetching diary for {current}: {e}")

        current += timedelta(days=1)

    logger.info(f"Extracted {len(all_foods)} unique foods from {start_date} to {end_date}")

    # Load and validate against schema
    schema = _load_food_schema()
    foods_list = list(all_foods.values())

    # Validate each food against schema
    invalid_foods = []
    for food in foods_list:
        try:
            validate(instance=food, schema=schema)
        except ValidationError as e:
            logger.warning(f"Food '{food.get('name')}' failed schema validation: {e.message}")
            invalid_foods.append(food)

    # Remove invalid foods
    for food in invalid_foods:
        foods_list.remove(food)

    if invalid_foods:
        logger.warning(f"Removed {len(invalid_foods)} invalid foods that didn't match schema")

    # Save to disk
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_range = f"{start_date.isoformat()}_{end_date.isoformat()}"
    filename = f"food_data_{date_range}_{timestamp}.json"
    filepath = RAW_DATA_DIR / filename

    with open(filepath, 'w') as f:
        json.dump({
            "metadata": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "fetched_at": datetime.now().isoformat(),
                "food_count": len(foods_list),
            },
            "foods": foods_list
        }, f, indent=2)

    logger.info(f"Saved {len(foods_list)} valid foods to {filepath}")
    return str(filepath)


def _load_food_schema() -> dict:
    """Load MFP Food Fact schema from file."""
    try:
        with open(MFP_FOOD_SCHEMA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load MFP food schema: {e}")
        # Return a minimal schema to avoid complete failure
        return {"type": "object"}


def _safe_float(value) -> float:
    """Convert value to float, return 0 if None/invalid."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _get_measurement(entry) -> dict:
    """Extract measurement from entry as object with unit and value.

    Args:
        entry: MyFitnessPal Entry object

    Returns:
        Measurement dict with 'unit' (g or ml) and 'value' (numeric amount)
    """
    try:
        # Try to get quantity and unit from entry
        quantity = getattr(entry, "quantity", 1.0)
        unit = getattr(entry, "unit", "g")

        # Normalize unit to schema-valid values (g or ml)
        if not unit or unit.lower() not in ["g", "ml"]:
            unit = "g"
        else:
            unit = unit.lower()

        return {
            "unit": unit,
            "value": float(quantity)
        }
    except Exception as e:
        logger.debug(f"Failed to extract measurement: {e}")
        # Default to 1 gram
        return {"unit": "g", "value": 1.0}


def main():
    env_path = Path(__file__).parent.parent.parent / ".env.local"
    load_dotenv(env_path)

    parser = argparse.ArgumentParser(
        description="Download raw food data from MyFitnessPal API and save to disk"
    )

    # Authentication
    auth_group = parser.add_mutually_exclusive_group(required=True)
    auth_group.add_argument(
        "--username",
        help="MFP username or email"
    )
    auth_group.add_argument(
        "--cookie",
        help="MFP session cookie (__Secure-next-auth.session-token)"
    )

    parser.add_argument(
        "--password",
        help="MFP password (required if using --username)"
    )

    # Date range
    range_group = parser.add_mutually_exclusive_group(required=True)
    range_group.add_argument(
        "--today",
        action="store_true",
        help="Fetch only today's data"
    )
    range_group.add_argument(
        "--last-two-weeks",
        action="store_true",
        help="Fetch last 2 weeks of data"
    )
    range_group.add_argument(
        "--last-month",
        action="store_true",
        help="Fetch last 30 days of data"
    )
    range_group.add_argument(
        "--range-start",
        help="Start date (YYYY-MM-DD) - use with --range-end"
    )

    parser.add_argument(
        "--range-end",
        help="End date (YYYY-MM-DD) - use with --range-start"
    )

    args = parser.parse_args()

    # Validate authentication
    if args.username and not args.password:
        logger.error("--password is required when using --username")
        sys.exit(1)

    # Authenticate
    try:
        if args.username and args.password:
            logger.info(f"Authenticating with username: {args.username}")
            cookies, mfp_username = login_mfp_password(args.username, args.password)
            logger.info(f"✅ Authenticated as {mfp_username}")
        elif args.cookie:
            logger.info("Authenticating with session cookie")
            # For cookie auth, we need the username - check .env.local first
            username = os.getenv("MFP_USERNAME", "").strip()
            if not username:
                username = input("Enter MFP username for cookie auth: ").strip()
            if not username:
                logger.error("Username is required for cookie authentication")
                sys.exit(1)
            cookies, mfp_username = login_mfp_cookie(args.cookie, username)
            logger.info(f"✅ Authenticated as {mfp_username}")
    except Exception as e:
        logger.error(f"❌ Authentication failed: {e}")
        sys.exit(1)

    # Create client
    try:
        client = mfp_client.build_client(cookies, username=mfp_username)
    except Exception as e:
        logger.error(f"❌ Failed to create MFP client: {e}")
        sys.exit(1)

    # Parse date range
    start_date, end_date = parse_date_range(args)
    logger.info(f"Date range: {start_date} to {end_date}")

    # Fetch and save data
    try:
        filepath = fetch_and_save_food_data(client, start_date, end_date)
        logger.info(f"✅ Data saved to {filepath}")
    except Exception as e:
        logger.error(f"❌ Error fetching food data: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

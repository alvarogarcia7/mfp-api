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
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv

from ..mfp_auth import login_mfp_password, login_mfp_cookie
from ..vendor import mfp_client
from . import library, unit_cache, diary_sync

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
    units_cache = unit_cache.UnitMeasurementsCache()
    diary_manager = diary_sync.FoodDiarySyncManager()

    current = start_date
    while current <= end_date:
        try:
            logger.debug(f"Fetching diary for {current}")
            mfp_day = client.get_date(current)

            # Sync diary entry for this date
            diary_manager.add_diary_entry(current, mfp_day)

            for meal in mfp_day.meals:
                for entry in meal.entries:
                    name = entry.name

                    # Store first occurrence of each food (by name)
                    if name not in all_foods:
                        # Get measurement and raw entry data
                        measurement = _get_measurement(entry)
                        raw_data = _get_raw_entry_data(entry)

                        # Track units in cache
                        unit_name = measurement.get("unit")
                        if unit_name and unit_name not in units_cache.units:
                            unit_info = {
                                "unit_name": unit_name,
                                "measurement_unit_url": raw_data.get("measurement_unit_url"),
                                "first_seen": datetime.now().isoformat(),
                            }
                            units_cache.add_unit(unit_name, unit_info)

                        all_foods[name] = {
                            "name": name,
                            "measurement": measurement,
                            "download_url": raw_data.get("download_url"),
                            "measurement_unit_url": raw_data.get("measurement_unit_url"),
                            "raw": raw_data,
                            "calories": library.safe_float(entry.totals.get("calories")),
                            "protein": library.safe_float(entry.totals.get("protein")),
                            "carbs": library.safe_float(entry.totals.get("carbs")),
                            "fat": library.safe_float(entry.totals.get("fat")),
                            "fiber": library.safe_float(entry.totals.get("fiber")),
                            "sugar": library.safe_float(entry.totals.get("sugar")),
                            "sodium": library.safe_float(entry.totals.get("sodium")),
                            "cholesterol": library.safe_float(entry.totals.get("cholesterol")),
                            "saturated_fat": library.safe_float(entry.totals.get("saturated_fat")),
                            "potassium": library.safe_float(entry.totals.get("potassium")),
                        }

        except Exception as e:
            logger.warning(f"Error fetching diary for {current}: {e}")

        current += timedelta(days=1)

    # Save units cache
    units_cache.save()

    logger.info(f"Extracted {len(all_foods)} unique foods from {start_date} to {end_date}")

    # Load and validate against schema
    schema = library.load_schema(MFP_FOOD_SCHEMA_FILE)
    foods_list = list(all_foods.values())

    # Validate each food against schema and mark validity
    valid_count, invalid_count = library.validate_data(foods_list, schema, "food")

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
                "valid_count": valid_count,
                "invalid_count": invalid_count,
            },
            "foods": foods_list
        }, f, indent=2)

    logger.info(f"Saved {len(foods_list)} foods ({valid_count} valid, {invalid_count} invalid) to {filepath}")
    return str(filepath)




def _get_measurement(entry) -> dict:
    """Extract raw measurement from entry without processing.

    Args:
        entry: MyFitnessPal Entry object

    Returns:
        Measurement dict with raw 'unit' and 'value' from MFP
    """
    try:
        # Capture raw quantity and unit as-is from MFP
        quantity = getattr(entry, "quantity", None)
        unit = getattr(entry, "unit", None)

        return {
            "unit": unit,
            "value": float(quantity) if quantity is not None else None
        }
    except Exception as e:
        logger.debug(f"Failed to extract measurement: {e}")
        return {
            "unit": None,
            "value": None
        }


def _get_raw_entry_data(entry) -> dict:
    """Extract raw entry data and URLs from MFP entry object.

    Args:
        entry: MyFitnessPal Entry object

    Returns:
        Dict with raw JSON and URLs
    """
    try:
        # Extract URLs
        download_url = getattr(entry, "url", None)
        measurement_unit_url = None

        # Try to get measurement unit object and its URL
        unit_obj = getattr(entry, "unit_obj", None)
        if unit_obj and hasattr(unit_obj, "url"):
            measurement_unit_url = unit_obj.url

        # Store raw entry attributes as available
        raw_data = {
            "name": getattr(entry, "name", None),
            "quantity": getattr(entry, "quantity", None),
            "unit": getattr(entry, "unit", None),
            "download_url": download_url,
            "measurement_unit_url": measurement_unit_url,
        }

        # Store totals as raw data
        totals = getattr(entry, "totals", {})
        if totals:
            raw_data["totals"] = dict(totals) if hasattr(totals, "__iter__") else totals

        return raw_data
    except Exception as e:
        logger.debug(f"Failed to extract raw entry data: {e}")
        return {}


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
    try:
        start_date, end_date = library.parse_date_range(args)
    except ValueError as e:
        logger.error(f"❌ {e}")
        sys.exit(1)
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

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
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from mfp_auth import login_mfp_password, login_mfp_cookie
from vendor import mfp_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Raw data directory
RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw_food_data"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


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
                        all_foods[name] = {
                            "name": name,
                            "calories": _safe_float(entry.totals.get("calories")),
                            "protein": _safe_float(entry.totals.get("protein")),
                            "carbohydrates": _safe_float(entry.totals.get("carbohydrates")),
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
                "food_count": len(all_foods),
            },
            "foods": list(all_foods.values())
        }, f, indent=2)

    logger.info(f"Saved {len(all_foods)} foods to {filepath}")
    return str(filepath)


def _safe_float(value) -> float:
    """Convert value to float, return 0 if None/invalid."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def main():
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
            # For cookie auth, we need the username too
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
        client = mfp_client.build_client(cookies)
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

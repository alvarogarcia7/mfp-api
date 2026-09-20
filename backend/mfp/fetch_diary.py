#!/usr/bin/env python3
"""CLI script to download daily food diary from MyFitnessPal API.

Downloads complete daily diary entries (meals with all foods) for a date range
and saves raw JSON to disk.

Usage:
    python cli_fetch_diary.py --username user@example.com --password secret --today
    python cli_fetch_diary.py --username user@example.com --password secret --last-week
    python cli_fetch_diary.py --cookie <session_token> --range-start 2026-09-01 --range-end 2026-09-15
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

from ..mfp_auth import login_mfp_password, login_mfp_cookie
from ..vendor import mfp_client
from . import library

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Raw data directory
RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw_diary_data"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_and_save_daily_diary(client: mfp_client.CurlCffiClient, start_date: date, end_date: date) -> str:
    """Fetch daily diary entries and save to disk.

    Fetches complete daily food diary including all meals and food entries.

    Args:
        client: Authenticated MFP client
        start_date: Start date
        end_date: End date

    Returns:
        Path to saved JSON file
    """
    logger.info(f"Fetching daily food diary from {start_date} to {end_date}")

    diary_entries = []
    current_date = start_date

    while current_date <= end_date:
        try:
            logger.info(f"Fetching diary for {current_date.isoformat()}")

            # Fetch daily diary for this date
            diary = client.get_date(current_date)

            if diary:
                # Extract meals from diary
                meals_data = []
                for meal in diary.meals:
                    meal_data = {
                        "name": meal.name,
                        "entries": []
                    }

                    # Extract foods from each meal
                    for entry in meal.entries:
                        # Handle both dict and object-style access for entry totals
                        entry_totals = getattr(entry, "totals", {})
                        if isinstance(entry_totals, dict):
                            food_entry = {
                                "name": getattr(entry, "name", ""),
                                "quantity": library.safe_float(getattr(entry, "quantity", None)),
                                "unit": getattr(entry, "unit", ""),
                                "calories": library.safe_int(entry_totals.get("calories", 0)),
                                "protein": library.safe_float(entry_totals.get("protein", None)),
                                "carbs": library.safe_float(entry_totals.get("carbs", None)),
                                "fat": library.safe_float(entry_totals.get("fat", None)),
                            }
                        else:
                            food_entry = {
                                "name": getattr(entry, "name", ""),
                                "quantity": library.safe_float(getattr(entry, "quantity", None)),
                                "unit": getattr(entry, "unit", ""),
                                "calories": library.safe_int(getattr(entry_totals, "calories", 0)),
                                "protein": library.safe_float(getattr(entry_totals, "protein", None)),
                                "carbs": library.safe_float(getattr(entry_totals, "carbs", None)),
                                "fat": library.safe_float(getattr(entry_totals, "fat", None)),
                            }
                        meal_data["entries"].append(food_entry)

                    meals_data.append(meal_data)

                # Create daily diary entry
                # Handle both dict and object-style access for totals
                totals = diary.totals if diary.totals else {}
                if isinstance(totals, dict):
                    daily_totals = {
                        "calories": library.safe_int(totals.get("calories", 0)),
                        "protein": library.safe_float(totals.get("protein", 0.0)),
                        "carbs": library.safe_float(totals.get("carbs", 0.0)),
                        "fat": library.safe_float(totals.get("fat", 0.0)),
                    }
                else:
                    daily_totals = {
                        "calories": library.safe_int(getattr(totals, "calories", 0)),
                        "protein": library.safe_float(getattr(totals, "protein", 0.0)),
                        "carbs": library.safe_float(getattr(totals, "carbs", 0.0)),
                        "fat": library.safe_float(getattr(totals, "fat", 0.0)),
                    }

                daily_entry = {
                    "date": current_date.isoformat(),
                    "synced_at": datetime.now().isoformat(),
                    "meals": meals_data,
                    "totals": daily_totals,
                    "meal_count": len(meals_data),
                    "total_foods": sum(len(m["entries"]) for m in meals_data),
                }
                diary_entries.append(daily_entry)
            else:
                logger.debug(f"No diary data for {current_date}")

            # Move to next date
            current_date = current_date + timedelta(days=1)
        except Exception as e:
            logger.error(f"Error fetching diary for {current_date}: {e}", exc_info=True)
            current_date = current_date + timedelta(days=1)

    logger.info(f"Fetched {len(diary_entries)} daily diary entries")

    # Save to disk
    date_range = f"{start_date.isoformat()}_{end_date.isoformat()}"
    return library.save_raw_data(
        {
            "metadata": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "fetched_at": datetime.now().isoformat(),
                "entry_count": len(diary_entries),
            },
            "diary_entries": diary_entries
        },
        f"diary_{date_range}",
        RAW_DATA_DIR
    )


def main():
    # Load environment variables from .env.local
    env_path = Path(__file__).parent.parent.parent / ".env.local"
    load_dotenv(env_path)

    parser = argparse.ArgumentParser(
        description="Download daily food diary from MyFitnessPal and save to disk",
        epilog="Credentials can be provided via arguments, .env.local, or will prompt interactively."
    )

    # Authentication options
    parser.add_argument("--username", help="MyFitnessPal username/email")
    parser.add_argument("--password", help="MyFitnessPal password")
    parser.add_argument("--cookie", help="MyFitnessPal session cookie (alternative to username/password)")

    # Date range
    range_group = parser.add_mutually_exclusive_group(required=True)
    range_group.add_argument("--today", action="store_true", help="Fetch only today's diary")
    range_group.add_argument("--last-week", action="store_true", help="Fetch last 7 days")
    range_group.add_argument("--last-two-weeks", action="store_true", help="Fetch last 2 weeks")
    range_group.add_argument("--last-month", action="store_true", help="Fetch last 30 days")
    range_group.add_argument("--range-start", help="Start date (YYYY-MM-DD) - use with --range-end")

    parser.add_argument("--range-end", help="End date (YYYY-MM-DD) - use with --range-start")

    args = parser.parse_args()

    # Get credentials
    username = args.username or os.getenv("MFP_USERNAME")
    password = args.password or os.getenv("MFP_PASSWORD")
    cookie = args.cookie or os.getenv("MFP_COOKIE")

    # Authenticate
    try:
        if username and password:
            logger.info(f"Authenticating with username: {username}")
            cookies, mfp_username = login_mfp_password(username, password)
            logger.info(f"✅ Authenticated as {mfp_username}")
        elif cookie:
            logger.info("Authenticating with session cookie")
            # For cookie auth, we need the username - check .env.local first
            mfp_username = os.getenv("MFP_USERNAME", "").strip()
            if not mfp_username:
                mfp_username = input("Enter MFP username for cookie auth: ").strip()
            if not mfp_username:
                logger.error("Username is required for cookie authentication")
                sys.exit(1)
            cookies, mfp_username = login_mfp_cookie(cookie, mfp_username)
            logger.info(f"✅ Authenticated as {mfp_username}")
        else:
            logger.error("❌ No credentials provided")
            logger.error("   Use --username/--password or --cookie, or set MFP_USERNAME/MFP_PASSWORD/MFP_COOKIE in .env.local")
            sys.exit(1)
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

    # Fetch and save
    try:
        filepath = fetch_and_save_daily_diary(client, start_date, end_date)
        logger.info(f"✅ Diary data saved to {filepath}")
    except Exception as e:
        logger.error(f"❌ Error fetching diary: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

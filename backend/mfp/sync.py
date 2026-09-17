#!/usr/bin/env python3
"""CLI script to sync local food entries to MyFitnessPal.

Takes food entries from the local diary and syncs them to MFP API.
Credentials loaded from .env.local (MFP_USERNAME, MFP_PASSWORD or MFP_SESSION_COOKIE).

Usage:
    python cli_sync_to_mfp.py                # Sync all pending entries
    python cli_sync_to_mfp.py --date 2026-09-15  # Sync specific date
    python cli_sync_to_mfp.py --mark-synced  # Mark entries as synced after completion
"""

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

from ..mfp_auth import login_mfp_password, login_mfp_cookie
from ..vendor import mfp_client, diary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
env_path = Path(__file__).parent.parent / ".env.local"
load_dotenv(env_path)


def get_client():
    """Authenticate and get MFP client."""
    username = os.getenv("MFP_USERNAME")
    password = os.getenv("MFP_PASSWORD")
    cookie = os.getenv("MFP_SESSION_COOKIE")

    if not username:
        logger.error("❌ MFP_USERNAME not found in .env.local")
        sys.exit(1)

    try:
        if cookie:
            logger.info(f"Authenticating with session cookie for {username}")
            cookies, mfp_username = login_mfp_cookie(cookie, username)
        elif password:
            logger.info(f"Authenticating with password for {username}")
            cookies, mfp_username = login_mfp_password(username, password)
        else:
            logger.error("❌ Neither MFP_PASSWORD nor MFP_SESSION_COOKIE found in .env.local")
            sys.exit(1)

        logger.info(f"✅ Authenticated as {mfp_username}")
        client = mfp_client.build_client(cookies)
        return client

    except Exception as e:
        logger.error(f"❌ Authentication failed: {e}")
        sys.exit(1)


def load_food_entries() -> dict:
    """Load food entries from local diary.

    Returns dict: {date -> {meal -> [entries]}}
    """
    # Note: In real app, this would be read from persistent storage
    # For now, we'll note that this data is managed by the web app
    logger.warning("⚠️  Food entries are managed by the web app (in-memory)")
    logger.warning("   To persist entries, they need to be saved to a file")
    return {}


def sync_entry_to_mfp(client, entry_date: date, meal: str, entry: dict) -> bool:
    """Sync a single food entry to MFP.

    Args:
        client: Authenticated MFP client
        entry_date: Date of entry
        meal: Meal type (breakfast, lunch, dinner, snacks)
        entry: Entry dict with name, calories, quantity, etc.

    Returns:
        True if successful, False otherwise
    """
    try:
        food_name = entry.get("name")
        quantity = entry.get("quantity", 1.0)

        logger.info(f"Syncing: {food_name} ({quantity}g) to {meal} on {entry_date}")

        # Search for food in MFP
        results = diary.search_food(client, food_name, limit=1, with_macros=True)

        if not results:
            logger.warning(f"  ⚠️  Food '{food_name}' not found in MFP")
            return False

        food_result = results[0]
        food_id = food_result.get("food_id")
        weight_id = food_result.get("weight_id", "100")

        logger.debug(f"  Found: {food_result.get('name')} (ID: {food_id})")

        # Get diary page to extract CSRF token
        diary_html, csrf = diary.diary_page(client, entry_date)

        # Add food to diary
        diary.add_food_to_diary(
            client,
            food_id,
            weight_id,
            csrf,
            meal,
            entry_date,
            float(quantity)
        )

        logger.info(f"  ✅ Synced: {food_name}")
        return True

    except Exception as e:
        logger.error(f"  ❌ Error syncing '{food_name}': {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Sync local food entries to MyFitnessPal"
    )

    parser.add_argument(
        "--date",
        help="Sync entries for specific date (YYYY-MM-DD). Default: today"
    )

    parser.add_argument(
        "--all-dates",
        action="store_true",
        help="Sync all pending entries from all dates"
    )

    parser.add_argument(
        "--mark-synced",
        action="store_true",
        help="Mark entries as synced after successful sync (removes from local diary)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without actually syncing"
    )

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("MyFitnessPal Food Entry Sync")
    logger.info("=" * 70)
    logger.info("")

    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
        logger.info("")

    # Get MFP client
    client = get_client()

    # Load local entries
    entries = load_food_entries()

    if not entries:
        logger.warning("⚠️  No local food entries to sync")
        logger.info("")
        logger.info("Note: The web app manages food entries in-memory.")
        logger.info("To enable persistence, entries need to be saved to disk.")
        sys.exit(1)

    # Determine which dates to sync
    if args.all_dates:
        dates_to_sync = list(entries.keys())
    elif args.date:
        dates_to_sync = [args.date]
    else:
        dates_to_sync = [date.today().isoformat()]

    # Sync entries
    total_synced = 0
    total_failed = 0

    for date_str in sorted(dates_to_sync):
        logger.info(f"Syncing entries for {date_str}:")
        entry_date = date.fromisoformat(date_str)
        meals = entries.get(date_str, {})

        for meal, meal_entries in meals.items():
            for idx, entry in enumerate(meal_entries):
                if args.dry_run:
                    logger.info(f"  [DRY RUN] Would sync: {entry.get('name')} to {meal}")
                else:
                    success = sync_entry_to_mfp(client, entry_date, meal, entry)
                    if success:
                        total_synced += 1
                    else:
                        total_failed += 1

    logger.info("")
    logger.info("=" * 70)
    logger.info(f"✅ Sync Complete")
    logger.info(f"   Synced: {total_synced}")
    logger.info(f"   Failed: {total_failed}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()

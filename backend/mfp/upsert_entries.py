#!/usr/bin/env python3
"""CLI script to sync local food entries to MyFitnessPal.

Reads entries from .food_entries.json where replicatedToMFP=false,
syncs them to MFP API, then marks them as replicatedToMFP=true.

Usage:
    python -m backend.mfp.upsert_entries                    # Sync all pending
    python -m backend.mfp.upsert_entries --date 2026-09-15  # Sync specific date
    python -m backend.mfp.upsert_entries --dry-run           # Preview sync
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
from ..vendor import mfp_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
FOOD_ENTRIES_FILE = Path(__file__).parent.parent / ".food_entries.json"
env_path = Path(__file__).parent.parent.parent / ".env.local"
load_dotenv(env_path)


def load_entries() -> dict:
    """Load food entries from disk."""
    if not FOOD_ENTRIES_FILE.exists():
        return {}
    try:
        with open(FOOD_ENTRIES_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading entries: {e}")
        return {}


def save_entries(entries: dict) -> None:
    """Save food entries to disk."""
    try:
        with open(FOOD_ENTRIES_FILE, 'w') as f:
            json.dump(entries, f, indent=2)
        logger.info(f"✅ Saved entries to {FOOD_ENTRIES_FILE}")
    except Exception as e:
        logger.error(f"Error saving entries: {e}")


def get_pending_entries(entries: dict, date_filter: str = None) -> list:
    """Get entries where replicatedToMFP=false.

    Args:
        entries: All entries dict
        date_filter: Optional specific date to sync (YYYY-MM-DD)

    Returns:
        List of (date_str, meal, index, entry) tuples
    """
    pending = []
    for date_str, meals in entries.items():
        if date_filter and date_str != date_filter:
            continue
        for meal, food_list in meals.items():
            for idx, entry in enumerate(food_list):
                if not entry.get("replicatedToMFP", False):
                    pending.append((date_str, meal, idx, entry))
    return pending


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
        client = mfp_client.build_client(cookies, username=mfp_username)
        return client

    except Exception as e:
        logger.error(f"❌ Authentication failed: {e}")
        sys.exit(1)


def sync_entry_to_mfp(client, entry_date: str, meal: str, entry: dict) -> bool:
    """Sync a single food entry to MFP.

    Args:
        client: Authenticated MFP client
        entry_date: Date of entry (YYYY-MM-DD)
        meal: Meal type (breakfast, lunch, dinner, snacks)
        entry: Entry dict with name, calories, quantity

    Returns:
        True if successful, False otherwise
    """
    try:
        food_name = entry.get("name", "")
        if not isinstance(food_name, str) or not food_name:
            logger.warning(f"Entry missing valid food name on {entry_date}")
            return False

        quantity = entry.get("quantity", 1.0)
        calories = entry.get("calories", 0)

        logger.info(f"  Syncing: {food_name} ({quantity}g, {calories} cal) → {meal} on {entry_date}")

        # Use the myfitnesspal client to add food
        # The client.get_date() returns a date object we can add to
        target_date = __import__('datetime').datetime.strptime(entry_date, '%Y-%m-%d').date()
        mfp_date = client.get_date(target_date)

        # Add to the appropriate meal
        mfp_date.add_food(food_name, meal, quantity, calories)
        logger.info(f"  ✅ Synced to MFP")
        return True

    except Exception as e:
        logger.warning(f"  ⚠️  Could not sync {entry.get('name')}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Sync local food entries to MyFitnessPal",
        epilog="Syncs all pending entries (replicatedToMFP=false) to MFP and marks them as replicated."
    )
    parser.add_argument("--date", help="Sync specific date only (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be synced without actually syncing")

    args = parser.parse_args()

    # Load entries
    entries = load_entries()
    if not entries:
        logger.info("No entries to sync")
        return

    # Get pending entries
    pending = get_pending_entries(entries, args.date)
    if not pending:
        logger.info("No pending entries to sync")
        return

    logger.info(f"Found {len(pending)} pending entries to sync")

    if args.dry_run:
        logger.info("🔍 DRY RUN - would sync:")
        for date_str, meal, idx, entry in pending:
            logger.info(f"  {date_str} {meal}: {entry['name']} ({entry.get('calories', 0)} cal)")
        return

    # Authenticate
    client = get_client()

    # Sync entries
    synced_count = 0
    for date_str, meal, idx, entry in pending:
        if sync_entry_to_mfp(client, date_str, meal, entry):
            # Mark as replicated
            entries[date_str][meal][idx]["replicatedToMFP"] = True
            synced_count += 1

    # Save updated entries
    if synced_count > 0:
        save_entries(entries)
        logger.info(f"✅ Successfully synced {synced_count}/{len(pending)} entries")
    else:
        logger.warning(f"⚠️  Could not sync any entries")


if __name__ == "__main__":
    main()

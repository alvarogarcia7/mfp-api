#!/usr/bin/env python3
"""CLI script to download raw Polar Flow calendar events data.

Downloads calendar events for a date range and saves raw JSON to disk.
Useful for building and updating the exercise database.

Usage:
    python cli_fetch_polar_data.py --cookie <token> --today
    python cli_fetch_polar_data.py --cookie <token> --last-two-weeks
    python cli_fetch_polar_data.py --cookie <token> --last-month
    python cli_fetch_polar_data.py --cookie <token> --range-start 2026-09-01 --range-end 2026-09-15
"""

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from curl_cffi import requests as curl_cffi_requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Raw data directory
RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw_polar_data"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Polar Flow API
POLAR_API_BASE = "https://flow.polar.com"


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


def format_polar_date(d: date) -> str:
    """Convert date to Polar Flow format (D.M.Y)."""
    return f"{d.day}.{d.month}.{d.year}"


def fetch_and_save_polar_data(session, start_date: date, end_date: date) -> str:
    """Fetch calendar events from Polar Flow for date range and save to disk.

    Args:
        session: Requests session with authentication
        start_date: Start date
        end_date: End date

    Returns:
        Path to saved JSON file
    """
    logger.info(f"Fetching Polar Flow calendar events from {start_date} to {end_date}")

    # Convert to Polar date format (D.M.Y)
    start_polar = format_polar_date(start_date)
    end_polar = format_polar_date(end_date)

    try:
        # Fetch calendar events
        url = f"{POLAR_API_BASE}/training/getCalendarEvents"
        params = {
            "start": start_polar,
            "end": end_polar,
        }

        logger.debug(f"Request URL: {url}")
        logger.debug(f"Request params: {params}")

        response = session.get(url, params=params, timeout=30)

        logger.debug(f"Response status: {response.status_code}")

        if response.status_code == 401:
            logger.error("Polar Flow returned 401 Unauthorized")
            raise Exception("HTTP 401: Invalid Polar Flow credentials or expired session. Please update your cookie.")

        if response.status_code == 404:
            logger.error(f"Polar Flow API returned 404. URL: {response.url}")
            raise Exception(f"HTTP 404: Polar Flow API endpoint not found.")

        response.raise_for_status()

        data = response.json()

        # Log data structure for debugging
        if isinstance(data, list):
            logger.info(f"Fetched {len(data)} calendar events from Polar Flow")
        elif isinstance(data, dict):
            events = data.get("events", [])
            logger.info(f"Fetched {len(events)} calendar events from Polar Flow")
        else:
            logger.warning(f"Unexpected response format: {type(data)}")
            events = []

        # Save to disk
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_range = f"{start_date.isoformat()}_{end_date.isoformat()}"
        filename = f"polar_calendar_{date_range}_{timestamp}.json"
        filepath = RAW_DATA_DIR / filename

        with open(filepath, 'w') as f:
            json.dump({
                "metadata": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "polar_start": start_polar,
                    "polar_end": end_polar,
                    "fetched_at": datetime.now().isoformat(),
                    "event_count": len(data) if isinstance(data, list) else len(data.get("events", [])),
                },
                "raw_response": data
            }, f, indent=2)

        logger.info(f"Saved calendar data to {filepath}")
        return str(filepath)

    except Exception as e:
        logger.error(f"Error fetching Polar Flow calendar data: {e}", exc_info=True)
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Download raw calendar events data from Polar Flow and save to disk"
    )

    # Authentication
    parser.add_argument(
        "--cookie",
        required=True,
        help="Polar Flow session cookie (full cookie string with all cookies)"
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

    # Create session with authentication
    try:
        logger.info("Setting up Polar Flow session")
        session = curl_cffi_requests.Session(impersonate="chrome")

        # Set cookies
        session.headers["Cookie"] = args.cookie

        # Set required headers
        session.headers.update({
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "x-requested-with": "XMLHttpRequest",
        })

        logger.info("✅ Session configured")
    except Exception as e:
        logger.error(f"❌ Failed to create session: {e}")
        sys.exit(1)

    # Parse date range
    start_date, end_date = parse_date_range(args)
    logger.info(f"Date range: {start_date} to {end_date}")

    # Fetch and save data
    try:
        filepath = fetch_and_save_polar_data(session, start_date, end_date)
        logger.info(f"✅ Data saved to {filepath}")
    except Exception as e:
        logger.error(f"❌ Error fetching Polar Flow data: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

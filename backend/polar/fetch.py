#!/usr/bin/env python3
"""CLI script to download raw Polar Flow calendar events data.

Downloads calendar events for a date range and saves raw JSON to disk.
Credentials are loaded from .env.local (POLAR_FLOW_COOKIE).

Usage:
    python cli_fetch_polar_data.py --today
    python cli_fetch_polar_data.py --last-two-weeks
    python cli_fetch_polar_data.py --last-month
    python cli_fetch_polar_data.py --range-start 2026-09-01 --range-end 2026-09-15
    python cli_fetch_polar_data.py --cookie <token> --today  # Override .env.local
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
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


def get_last_entry_date() -> date | None:
    """Get the date of the last parsed exercise entry.

    Reads from .exercise_cache.json to find the most recent entry date.

    Returns:
        Date of last entry or None if no entries found
    """
    exercise_cache = RAW_DATA_DIR.parent / ".exercise_cache.json"

    if not exercise_cache.exists():
        return None

    try:
        with open(exercise_cache, 'r') as f:
            exercises = json.load(f)

        if not exercises:
            return None

        # Find latest date from all exercises
        latest_date = None
        for exercise in exercises:
            entry_date_str = exercise.get("date")
            if entry_date_str:
                try:
                    entry_date = date.fromisoformat(entry_date_str)
                    if latest_date is None or entry_date > latest_date:
                        latest_date = entry_date
                except ValueError:
                    continue

        return latest_date

    except Exception as e:
        logger.warning(f"Failed to read last entry date: {e}")
        return None


def parse_date_range(args) -> tuple[date, date]:
    """Parse date range from CLI arguments."""
    today = date.today()

    if args.today:
        return today, today
    elif args.since_last_entry:
        last_date = get_last_entry_date()
        if last_date:
            logger.info(f"Last entry found on {last_date}, fetching from {last_date} to today")
            return last_date, today
        else:
            logger.warning("No previous entries found, fetching last 30 days instead")
            start = today - timedelta(days=30)
            return start, today
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
        logger.error("Must specify one of: --today, --since-last-entry, --last-two-weeks, --last-month, or --range-start/--range-end")
        sys.exit(1)


def format_polar_date(d: date) -> str:
    """Convert date to Polar Flow API format (D.M.Y)."""
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
        logger.debug(f"Response headers: {response.headers}")
        logger.debug(f"Response content length: {len(response.content)}")

        if response.status_code == 401:
            logger.error("Polar Flow returned 401 Unauthorized")
            raise Exception("HTTP 401: Invalid Polar Flow credentials or expired session. Please update your cookie.")

        if response.status_code == 403:
            logger.error("Polar Flow returned 403 Forbidden - Missing required session cookies")
            raise Exception("HTTP 403: Missing required session cookies (PLAY_SESSION_FLOW, AWSALB). Get full cookie string from browser DevTools.")

        if response.status_code == 404:
            logger.error(f"Polar Flow API returned 404. URL: {response.url}")
            raise Exception(f"HTTP 404: Polar Flow API endpoint not found.")

        response.raise_for_status()

        # Log response content for debugging if it's small
        if len(response.content) < 1000:
            logger.debug(f"Response content: {response.text}")

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
    # Load environment variables from .env.local
    env_path = Path(__file__).parent.parent.parent / ".env.local"
    load_dotenv(env_path)

    parser = argparse.ArgumentParser(
        description="Download raw calendar events data from Polar Flow and save to disk",
        epilog="Credentials are loaded from .env.local. Use --cookie to override."
    )

    # Authentication (optional if .env.local is set)
    parser.add_argument(
        "--cookie",
        help="Polar Flow session cookie (overrides .env.local POLAR_FLOW_COOKIE)"
    )

    # Date range
    range_group = parser.add_mutually_exclusive_group(required=True)
    range_group.add_argument(
        "--today",
        action="store_true",
        help="Fetch only today's data"
    )
    range_group.add_argument(
        "--since-last-entry",
        action="store_true",
        help="Fetch from last parsed entry date until today (incremental update)"
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

    # Get cookie from args or environment
    cookie = args.cookie or os.getenv("POLAR_FLOW_COOKIE")

    if not cookie:
        logger.error("❌ Polar Flow session cookie not found")
        logger.error("   Set POLAR_FLOW_COOKIE in .env.local or use --cookie argument")
        logger.error("")
        logger.error("   To get your full cookie string (includes FLOW_SESSION, PLAY_SESSION_FLOW, etc):")
        logger.error("   1. Log in to https://flow.polar.com/")
        logger.error("   2. Open DevTools (F12) → Network → select any API request to /api/diary/*")
        logger.error("   3. In the Request Headers section, copy the entire 'Cookie' header value")
        logger.error("   4. Paste into .env.local as: POLAR_FLOW_COOKIE=<full_cookie_string>")
        logger.error("")
        logger.error("   The cookie must include:")
        logger.error("   - FLOW_SESSION=<jwt_token>")
        logger.error("   - PLAY_SESSION_FLOW=<session_token>")
        logger.error("   - AWSALB=<load_balancer_token>")
        logger.error("   - AWSALBCORS=<cors_token>")
        sys.exit(1)

    # Create session with authentication
    try:
        logger.info("Setting up Polar Flow session")
        session = curl_cffi_requests.Session(impersonate="chrome")

        # Set cookies (format: FLOW_SESSION=<jwt_token>)
        # If cookie is just the token, wrap it with FLOW_SESSION= prefix
        if cookie.startswith("eyJ"):  # JWT tokens start with eyJ (base64 for {"})
            cookie_header = f"FLOW_SESSION={cookie}"
        else:
            cookie_header = cookie
        session.headers["Cookie"] = cookie_header

        # Set required headers (matching Polar Flow web client)
        session.headers.update({
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "referer": "https://flow.polar.com/diary",
            "sec-ch-ua": '"Chromium";v="152", "Not?A_Brand";v="24", "Google Chrome";v="152"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
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

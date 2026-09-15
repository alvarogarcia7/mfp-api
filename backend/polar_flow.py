"""Polar Flow API integration for syncing cardio activities to MFP.

Fetches activities from Polar Flow and creates cardio entries in MyFitnessPal.
Supports VCR.py traffic recording/replay for offline testing.
"""

import logging
from datetime import date, timedelta
from typing import Optional
import requests
from curl_cffi import requests as curl_cffi_requests
import vcr
from pathlib import Path

logger = logging.getLogger(__name__)

# VCR cassettes for Polar Flow API
POLAR_CASSETTES_DIR = Path(__file__).parent / ".cassettes"
POLAR_CASSETTES_DIR.mkdir(exist_ok=True)

polar_vcr = vcr.VCR(
    serializer='json',
    cassette_library_dir=str(POLAR_CASSETTES_DIR),
    record_mode='once',
    match_on=['method', 'scheme', 'host', 'port', 'path', 'query'],
)

# Polar Flow API endpoints
POLAR_API_BASE = "https://www.polaraccesslink.com"
POLAR_FLOW_BASE = "https://flow.polar.com"


class PolarFlowClient:
    """Client for interacting with Polar Flow API."""

    def __init__(self, cookie: str, username: str):
        """Initialize Polar Flow client.

        Args:
            cookie: Polar Flow session cookie
            username: Polar Flow username
        """
        self.cookie = cookie
        self.username = username
        self.session = None
        self._setup_session()

    def _setup_session(self):
        """Set up HTTP session with authentication."""
        self.session = curl_cffi_requests.Session(impersonate="chrome")

        # Parse cookie into session
        if "=" in self.cookie:
            # Cookie header format
            self.session.cookies.set_cookie(
                requests.cookies.create_cookie(
                    domain=".polar.com",
                    name="",  # Will be parsed from cookie
                    value=self.cookie
                )
            )
        else:
            # Raw token format
            self.session.cookies.set("polar_session", self.cookie)

        # Set common headers
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def get_activities(self, start_date: date, end_date: date, use_vcr: bool = True) -> list[dict]:
        """Fetch activities from Polar Flow for a date range.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            use_vcr: If True, use VCR cassettes for recording/replaying traffic

        Returns:
            List of activity dicts with fields: name, duration_minutes, calories, date
        """
        def _fetch():
            activities = []
            try:
                # Polar Flow API endpoint for activities
                url = f"{POLAR_FLOW_BASE}/api/user/{self.username}/activities"
                params = {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                }

                logger.info(f"Fetching Polar Flow activities from {start_date} to {end_date}")
                logger.debug(f"Request URL: {url}")
                logger.debug(f"Request params: {params}")
                logger.debug(f"Request headers: {self.session.headers}")

                response = self.session.get(url, params=params, timeout=30)

                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response URL: {response.url}")

                if response.status_code == 404:
                    logger.error(f"Polar Flow API returned 404. URL: {response.url}")
                    logger.error(f"This may indicate: invalid username, wrong API endpoint, or missing authentication")
                    raise Exception(f"HTTP 404: Polar Flow API endpoint not found. Check username and credentials.")

                response.raise_for_status()

                data = response.json()
                activities_list = data.get("activities", [])

                logger.info(f"Fetched {len(activities_list)} activities from Polar Flow")

                # Parse activities
                for activity in activities_list:
                    parsed_activity = self._parse_activity(activity)
                    if parsed_activity:
                        activities.append(parsed_activity)

                return activities

            except Exception as e:
                logger.error(f"Error fetching Polar Flow activities: {e}", exc_info=True)
                raise

        # Use VCR cassette for recording/replaying traffic
        if use_vcr:
            cassette_name = f"polar_activities_{start_date.isoformat()}_{end_date.isoformat()}"
            with polar_vcr.use_cassette(f"{cassette_name}.json"):
                return _fetch()
        else:
            return _fetch()

    def _parse_activity(self, activity: dict) -> Optional[dict]:
        """Parse raw activity data from Polar Flow.

        Args:
            activity: Raw activity dict from API

        Returns:
            Parsed activity dict or None if parsing failed
        """
        try:
            # Extract activity fields
            activity_type = activity.get("type", "Unknown")
            start_time = activity.get("start_time", "")
            duration_seconds = activity.get("duration", 0)  # In seconds
            calories = activity.get("calories", 0)

            if not duration_seconds or not calories:
                logger.debug(f"Skipping activity: missing duration or calories")
                return None

            # Convert seconds to minutes
            duration_minutes = int(duration_seconds / 60)

            # Extract date from start_time
            try:
                activity_date = start_time.split("T")[0]
            except (IndexError, AttributeError):
                activity_date = date.today().isoformat()

            return {
                "name": f"Polar Flow - {activity_type}",
                "type": activity_type,
                "duration_minutes": duration_minutes,
                "calories": int(calories),
                "date": activity_date,
                "start_time": start_time,
                "raw_data": activity
            }

        except Exception as e:
            logger.error(f"Error parsing activity: {e}")
            return None

    def validate_connection(self) -> bool:
        """Validate that Polar Flow connection is working.

        Returns:
            True if connection is valid, False otherwise
        """
        try:
            url = f"{POLAR_FLOW_BASE}/api/user/{self.username}"
            response = self.session.get(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Polar Flow connection validation failed: {e}")
            return False


def create_polar_client(cookie: str, username: str) -> PolarFlowClient:
    """Create a Polar Flow client instance."""
    return PolarFlowClient(cookie, username)

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

    def __init__(self, cookie: str, username: str, user_id: str = None):
        """Initialize Polar Flow client.

        Args:
            cookie: Polar Flow session cookie (full cookie string including FLOW_SESSION)
            username: Polar Flow username
            user_id: Polar Flow user ID (required for API calls)
        """
        self.cookie = cookie
        self.username = username
        self.user_id = user_id or self._extract_user_id()
        self.session = None
        self._setup_session()

    def _extract_user_id(self) -> str:
        """Try to extract user ID from cookie string (if present)."""
        # User ID might be embedded in FLOW_SESSION cookie
        # Format: FLOW_SESSION=userid_...
        if "FLOW_SESSION" in self.cookie:
            parts = self.cookie.split("FLOW_SESSION=")
            if len(parts) > 1:
                session_part = parts[1].split(";")[0].split("_")
                if session_part:
                    try:
                        return session_part[0]
                    except:
                        pass
        return None

    def _setup_session(self):
        """Set up HTTP session with authentication."""
        self.session = curl_cffi_requests.Session(impersonate="chrome")

        # Set all cookies from the cookie string
        if self.cookie:
            self.session.headers["Cookie"] = self.cookie

        # Set required headers
        self.session.headers.update({
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "pragma": "no-cache",
            "x-requested-with": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
                if not self.user_id:
                    raise Exception("User ID is required. Please provide user_id when initializing the client.")

                # Polar Flow API endpoint for training history
                url = f"{POLAR_FLOW_BASE}/api/training/history"

                # Request body with userId and date range
                payload = {
                    "userId": self.user_id,
                    "fromDate": start_date.isoformat(),
                    "toDate": end_date.isoformat(),
                }

                logger.info(f"Fetching Polar Flow activities from {start_date} to {end_date}")
                logger.info(f"Using endpoint: {url}")
                logger.debug(f"Request payload: {payload}")
                logger.debug(f"Request headers: {dict(self.session.headers)}")

                response = self.session.post(url, json=payload, timeout=30)

                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response URL: {response.url}")

                if response.status_code == 401:
                    logger.error(f"Polar Flow returned 401 Unauthorized")
                    raise Exception(f"HTTP 401: Invalid Polar Flow credentials or expired session. Please update your cookie in .env.local.")

                if response.status_code == 404:
                    logger.error(f"Polar Flow API returned 404. URL: {response.url}")
                    raise Exception(f"HTTP 404: Polar Flow API endpoint not found. Check user_id and API endpoint.")

                response.raise_for_status()

                # Response is a direct array of activities
                activities_list = response.json()
                if not isinstance(activities_list, list):
                    logger.warning(f"Expected list response, got: {type(activities_list)}")
                    activities_list = activities_list.get("activities", []) if isinstance(activities_list, dict) else []

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
        """Parse raw activity data from Polar Flow training history.

        Args:
            activity: Raw activity dict from API
                    Expected fields: sportName, duration (ms), calories, startDate, etc.

        Returns:
            Parsed activity dict or None if parsing failed
        """
        try:
            # Extract activity fields from Polar Flow format
            sport_name = activity.get("sportName", "Unknown")
            duration_ms = activity.get("duration", 0)  # In milliseconds
            calories = activity.get("calories", 0)
            start_date = activity.get("startDate", "")  # Format: "2026-09-11 17:49:06.881"
            distance = activity.get("distance")  # Optional

            if not duration_ms or not calories:
                logger.debug(f"Skipping activity: missing duration or calories")
                return None

            # Convert milliseconds to minutes
            duration_minutes = int(duration_ms / 1000 / 60)

            # Extract date from startDate (format: "2026-09-11 17:49:06.881")
            try:
                activity_date = start_date.split(" ")[0] if " " in start_date else date.today().isoformat()
            except (IndexError, AttributeError):
                activity_date = date.today().isoformat()

            # Create activity name with sport type
            activity_name = f"Polar Flow - {sport_name}"

            parsed = {
                "name": activity_name,
                "sport_name": sport_name,
                "duration_minutes": duration_minutes,
                "calories": int(calories),
                "date": activity_date,
                "start_time": start_date,
                "id": activity.get("id"),
            }

            # Add optional fields
            if distance is not None:
                parsed["distance"] = distance
            if activity.get("hrAvg"):
                parsed["hr_avg"] = activity.get("hrAvg")

            return parsed

        except Exception as e:
            logger.error(f"Error parsing activity: {e}", exc_info=True)
            return None

    def validate_connection(self) -> bool:
        """Validate that Polar Flow connection is working.

        Returns:
            True if connection is valid, False otherwise
        """
        try:
            if not self.user_id:
                logger.error("Cannot validate connection: user_id is not set")
                return False

            # Try a minimal request to validate authentication
            url = f"{POLAR_FLOW_BASE}/api/training/history"
            today = date.today()
            payload = {
                "userId": self.user_id,
                "fromDate": today.isoformat(),
                "toDate": today.isoformat(),
            }

            logger.debug(f"Validating Polar Flow connection to {url}")
            response = self.session.post(url, json=payload, timeout=10)

            logger.debug(f"Validation response status: {response.status_code}")

            # Status 200 or 401 means endpoint exists (401 = auth issue, but endpoint is real)
            # 404 means wrong endpoint or completely wrong setup
            if response.status_code == 404:
                logger.error(f"Polar Flow API endpoint not found (404)")
                return False

            if response.status_code in [200, 401]:
                # 401 means auth failed but endpoint exists and is reachable
                if response.status_code == 401:
                    logger.warning("Polar Flow: authentication failed (401) - check credentials")
                    return False
                return True

            logger.warning(f"Unexpected response status: {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"Polar Flow connection validation failed: {e}")
            return False


def create_polar_client(cookie: str, username: str, user_id: str = None) -> PolarFlowClient:
    """Create a Polar Flow client instance.

    Args:
        cookie: Polar Flow session cookie (full cookie string)
        username: Polar Flow username
        user_id: Polar Flow user ID (required for API calls)

    Returns:
        PolarFlowClient instance
    """
    return PolarFlowClient(cookie, username, user_id)

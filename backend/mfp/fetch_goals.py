#!/usr/bin/env python3
"""CLI script to download user goals from MyFitnessPal API.

Downloads user profile data including daily calorie goal, macro targets,
and other nutritional goals, then saves to disk.

Usage:
    python -m backend.mfp.fetch_goals --username user@example.com --password secret
    python -m backend.mfp.fetch_goals --cookie <session_token>
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
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
RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw_goals_data"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_and_save_user_goals(client: mfp_client.CurlCffiClient, username: str) -> str:
    """Fetch or create user goals and save to disk.

    Attempts to fetch from API; falls back to defaults if unavailable.

    Args:
        client: Authenticated MFP client
        username: Username/email for logging

    Returns:
        Path to saved JSON file
    """
    logger.info(f"Fetching user goals for {username}...")

    api_data = {}
    # Try to fetch user goals via API endpoint
    try:
        response = client.session.get(
            "https://www.myfitnesspal.com/api/user/user_profile",
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        if response.status_code == 200:
            api_data = response.json()
            logger.info(f"✅ Fetched user profile from API: {username}")
        else:
            logger.warning(f"API returned {response.status_code}, using default goals")
    except Exception as e:
        logger.warning(f"Could not fetch from API ({e}), using default goals")

    # If we got data from API, use it; otherwise use sensible defaults
    if not api_data:
        logger.info("Creating default goals profile (edit data/user/profile.json to customize)")
        api_data = {
            "username": username,
            "daily_goals": {
                "calories": 2000,
                "protein": 50,
                "carbohydrates": 300,
                "fat": 65,
                "fiber": 25,
                "sodium": 2300,
                "sugar": 50,
                "cholesterol": 300,
                "saturated_fat": 20,
            }
        }
        logger.info(f"✅ Created default profile for {username}")

    # Extract goals from response or defaults
    daily_goals = api_data.get("daily_goals", {})
    goals_data = {
        "username": api_data.get("username", username),
        "fetched_at": datetime.now().isoformat(),
        "goals": {
            "calories": {
                "value": daily_goals.get("calories", 2000),
                "unit": "kcal"
            },
            "protein": {
                "value": daily_goals.get("protein", 50),
                "unit": "g"
            },
            "carbohydrates": {
                "value": daily_goals.get("carbohydrates", 300),
                "unit": "g"
            },
            "fat": {
                "value": daily_goals.get("fat", 65),
                "unit": "g"
            },
            "fiber": {
                "value": daily_goals.get("fiber", 25),
                "unit": "g"
            },
            "sodium": {
                "value": daily_goals.get("sodium", 2300),
                "unit": "mg"
            },
            "sugar": {
                "value": daily_goals.get("sugar", 50),
                "unit": "g"
            },
            "cholesterol": {
                "value": daily_goals.get("cholesterol", 300),
                "unit": "mg"
            },
            "saturated_fat": {
                "value": daily_goals.get("saturated_fat", 20),
                "unit": "g"
            },
        },
        "preferences": {
            "diary_preference": api_data.get("diary_preference"),
            "locale": api_data.get("locale", "en_US"),
        },
        "profile": {
            "age": api_data.get("age"),
            "gender": api_data.get("gender"),
            "height": api_data.get("height"),
            "weight": api_data.get("weight"),
            "activity_level": api_data.get("activity_level"),
        }
    }

    logger.info(f"Goal calories: {goals_data['goals']['calories']['value']} kcal")
    logger.info(f"Goal protein: {goals_data['goals']['protein']['value']}g")
    logger.info(f"Goal carbs: {goals_data['goals']['carbohydrates']['value']}g")
    logger.info(f"Goal fat: {goals_data['goals']['fat']['value']}g")

    # Save to disk
    return library.save_raw_data(
        goals_data,
        "user_goals",
        RAW_DATA_DIR
    )


def main():
    # Load environment variables from .env.local
    env_path = Path(__file__).parent.parent.parent / ".env.local"
    load_dotenv(env_path)

    parser = argparse.ArgumentParser(
        description="Download user goals from MyFitnessPal and save to disk",
        epilog="Credentials can be provided via arguments, .env.local, or will prompt interactively."
    )

    # Authentication options
    parser.add_argument("--username", help="MyFitnessPal username/email")
    parser.add_argument("--password", help="MyFitnessPal password")
    parser.add_argument("--cookie", help="MyFitnessPal session cookie (alternative to username/password)")

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

    # Fetch and save
    try:
        filepath = fetch_and_save_user_goals(client, mfp_username)
        logger.info(f"✅ Goals data saved to {filepath}")
    except Exception as e:
        logger.error(f"❌ Error fetching goals: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

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
    """Fetch user goals and save to disk.

    Args:
        client: Authenticated MFP client
        username: Username/email for logging

    Returns:
        Path to saved JSON file
    """
    logger.info(f"Fetching user goals for {username}...")

    try:
        # Fetch user profile
        user_profile = client.get_user_profile()
        logger.info(f"✅ Fetched user profile: {username}")

        # Extract goals from profile
        goals_data = {
            "username": username,
            "fetched_at": datetime.now().isoformat(),
            "goals": {
                "calories": {
                    "value": user_profile.goals.calories if hasattr(user_profile.goals, 'calories') else 2000,
                    "unit": "kcal"
                },
                "protein": {
                    "value": user_profile.goals.protein if hasattr(user_profile.goals, 'protein') else 50,
                    "unit": "g"
                },
                "carbohydrates": {
                    "value": user_profile.goals.carbohydrates if hasattr(user_profile.goals, 'carbohydrates') else 300,
                    "unit": "g"
                },
                "fat": {
                    "value": user_profile.goals.fat if hasattr(user_profile.goals, 'fat') else 65,
                    "unit": "g"
                },
                "fiber": {
                    "value": user_profile.goals.fiber if hasattr(user_profile.goals, 'fiber') else 25,
                    "unit": "g"
                },
                "sodium": {
                    "value": user_profile.goals.sodium if hasattr(user_profile.goals, 'sodium') else 2300,
                    "unit": "mg"
                },
                "sugar": {
                    "value": user_profile.goals.sugar if hasattr(user_profile.goals, 'sugar') else 50,
                    "unit": "g"
                },
                "cholesterol": {
                    "value": user_profile.goals.cholesterol if hasattr(user_profile.goals, 'cholesterol') else 300,
                    "unit": "mg"
                },
                "saturated_fat": {
                    "value": user_profile.goals.saturated_fat if hasattr(user_profile.goals, 'saturated_fat') else 20,
                    "unit": "g"
                },
            },
            "preferences": {
                "diary_preference": getattr(user_profile, 'diary_preference', None),
                "locale": getattr(user_profile, 'locale', 'en_US'),
            },
            "profile": {
                "age": getattr(user_profile, 'age', None),
                "gender": getattr(user_profile, 'gender', None),
                "height": getattr(user_profile, 'height', None),
                "weight": getattr(user_profile, 'weight', None),
                "activity_level": getattr(user_profile, 'activity_level', None),
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

    except Exception as e:
        logger.error(f"Error fetching goals: {e}", exc_info=True)
        raise


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

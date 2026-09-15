"""Mock MFP API with VCR.py traffic recording/replay capability.

This module provides:
1. A mock MFP client that can record real API calls to cassettes
2. Automatic replay of recorded traffic without hitting the real API
3. A transparent HTTP middleware to capture all traffic
"""

import json
import os
from pathlib import Path
from typing import Optional
import vcr
from functools import wraps

# Path to store recorded HTTP cassettes
CASSETTES_DIR = Path(__file__).parent / ".cassettes"
CASSETTES_DIR.mkdir(exist_ok=True)

# VCR configuration for recording/replaying HTTP traffic
my_vcr = vcr.VCR(
    serializer='json',
    cassette_library_dir=str(CASSETTES_DIR),
    record_mode='once',  # Record on first run, replay after
    match_on=['method', 'scheme', 'host', 'port', 'path', 'query'],
)


def record_http_traffic(cassette_name: str):
    """Decorator to record/replay HTTP traffic for a function.

    Usage:
        @record_http_traffic('mfp_login')
        def login_to_mfp(username, password):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with my_vcr.use_cassette(f"{cassette_name}.json"):
                return func(*args, **kwargs)
        return wrapper
    return decorator


class MockMFPClient:
    """Mock MFP client that can work offline using recorded traffic.

    Records real API calls on first run, then replays them from cassettes
    without needing internet connection on subsequent runs.
    """

    def __init__(self, use_cassettes: bool = True):
        """Initialize mock client.

        Args:
            use_cassettes: If True, use/record VCR cassettes for traffic
        """
        self.use_cassettes = use_cassettes
        self.cassettes = {}

    def get_or_create_cassette(self, name: str):
        """Get or create a VCR cassette context manager."""
        if name not in self.cassettes:
            self.cassettes[name] = my_vcr.use_cassette(f"{name}.json")
        return self.cassettes[name]

    def record_session_info(self, username: str, session_data: dict) -> None:
        """Record user session info for offline replay."""
        session_file = CASSETTES_DIR / f"session_{username}.json"
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)

    def load_session_info(self, username: str) -> Optional[dict]:
        """Load previously recorded session info."""
        session_file = CASSETTES_DIR / f"session_{username}.json"
        if session_file.exists():
            with open(session_file, 'r') as f:
                return json.load(f)
        return None


def get_mock_client(use_cassettes: bool = True) -> MockMFPClient:
    """Get a mock MFP client instance."""
    return MockMFPClient(use_cassettes=use_cassettes)

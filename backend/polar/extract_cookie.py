#!/usr/bin/env python3
"""Extract POLAR_FLOW_COOKIE from a curl request string.

Usage:
    python extract_cookie.py .env.polar.request.local

Reads a .env.polar.request.* file containing a curl command and extracts
the POLAR_FLOW_COOKIE from the -b (cookies) flag.
"""

import re
import sys
from pathlib import Path


def extract_cookie_from_curl(curl_command: str) -> str | None:
    """Extract POLAR_FLOW_COOKIE from a curl command string.

    Args:
        curl_command: The full curl command as a string

    Returns:
        The POLAR_FLOW_COOKIE value if found, None otherwise
    """
    # Find the -b flag (cookies) - can be "-b 'cookie_string'" or "-b \"cookie_string\""
    # The cookie value is in the form: FLOW_SESSION=<jwt_token>; other_cookies...

    # Match -b 'cookie string' or -b "cookie string" or -b cookie_string
    pattern = r"-b\s+['\"]?([^'\"]*FLOW_SESSION=[^'\"]*)['\"]?"
    match = re.search(pattern, curl_command, re.DOTALL)

    if match:
        cookie_string = match.group(1).strip()
        # Extract just the FLOW_SESSION part or the whole cookie string
        # If it contains FLOW_SESSION, extract from there to the end or to the next flag
        flow_session_match = re.search(r'(FLOW_SESSION=[^;]*)', cookie_string)
        if flow_session_match:
            return flow_session_match.group(1)
        return cookie_string

    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_cookie.py <.env.polar.request.local>")
        sys.exit(1)

    file_path = Path(sys.argv[1])

    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    try:
        with open(file_path, 'r') as f:
            curl_command = f.read()

        # Remove comments and join multiline curl commands
        lines = curl_command.split('\n')
        curl_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
        curl_string = ' '.join(curl_lines)

        cookie = extract_cookie_from_curl(curl_string)

        if cookie:
            print(f"POLAR_FLOW_COOKIE={cookie}")
            print("\n✅ Successfully extracted POLAR_FLOW_COOKIE")
            print("\nAdd this to your .env.local file:")
            print(f"POLAR_FLOW_COOKIE={cookie}")
        else:
            print("❌ Error: Could not find FLOW_SESSION cookie in curl command")
            print("\nMake sure your curl command includes the -b flag with cookies:")
            print("  Example: -b 'timezone=240; FLOW_SESSION=<jwt_token>; AWSALB=...'")
            sys.exit(1)

    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

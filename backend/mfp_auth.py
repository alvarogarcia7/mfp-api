"""MyFitnessPal authentication via credentials or session cookie."""

import logging
from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)


def parse_cookie_input(text: str) -> dict[str, str]:
    """Parse cookie input from various formats.

    Accepts:
    - Raw session token: abc123def456...
    - Cookie header: __Secure-next-auth.session-token=abc123; Path=/
    - Full header: Cookie: __Secure-next-auth.session-token=abc123; Path=/
    """
    text = text.strip()
    logger.debug(f"Parsing cookie input (length: {len(text)})")

    # Remove common prefixes
    if text.lower().startswith("cookie:"):
        text = text[7:].strip()
        logger.debug("Removed 'Cookie:' prefix")

    # If it looks like a cookie header (contains =), parse it
    if "=" in text:
        logger.debug("Detected cookie header format")
        cookies = {}
        for part in text.split(";"):
            if "=" in part:
                name, value = part.strip().split("=", 1)
                cookies[name.strip()] = value.strip()
        if cookies:
            logger.debug(f"Parsed {len(cookies)} cookies from header")
            return cookies

    # Otherwise treat as raw session token
    if text:
        logger.debug("Treating input as raw session token")
        return {"__Secure-next-auth.session-token": text}

    raise ValueError("Empty cookie input")


def login_mfp_password(username: str, password: str) -> tuple[dict[str, str], str]:
    """Login with username/password, extract session cookie.

    Returns (cookies_dict, mfp_username).
    Raises ValueError if login fails.
    """
    logger.info(f"Attempting password login for user: {username}")

    session = cffi_requests.Session(impersonate="chrome")
    logger.debug("Created curl_cffi session with Chrome impersonation")

    try:
        # Step 1: Get CSRF token
        logger.debug("Fetching CSRF token from https://www.myfitnesspal.com/api/auth/csrf")
        csrf_resp = session.get("https://www.myfitnesspal.com/api/auth/csrf")
        csrf_resp.raise_for_status()
        csrf_data = csrf_resp.json()

        if "csrfToken" not in csrf_data:
            logger.error("CSRF token not found in response")
            raise ValueError("Failed to get CSRF token from MFP")

        csrf_token = csrf_data["csrfToken"]
        logger.debug(f"Got CSRF token: {csrf_token[:20]}...")

        # Step 2: Login via NextAuth credentials callback
        logger.debug("Posting credentials to NextAuth callback endpoint")
        login_resp = session.post(
            "https://www.myfitnesspal.com/api/auth/callback/credentials",
            data={
                "csrfToken": csrf_token,
                "username": username,
                "password": password,
                "callbackUrl": "https://www.myfitnesspal.com/",
                "json": "true",
            },
        )
        login_resp.raise_for_status()
        logger.debug(f"Login response status: {login_resp.status_code}")

        # Step 3: Extract session token from cookies
        cookies = {k: v for k, v in session.cookies.items()}
        logger.debug(f"Extracted {len(cookies)} cookies from session")

        if "__Secure-next-auth.session-token" not in cookies:
            logger.error(f"Session token not found in cookies. Available: {list(cookies.keys())}")
            raise ValueError("Login failed — session token not received. Check credentials.")

        logger.info(f"Successfully logged in user: {username}")
        return cookies, username

    except Exception as e:
        logger.error(f"Password login failed: {str(e)}", exc_info=True)
        raise


def login_mfp_cookie(cookie_input: str) -> tuple[dict[str, str], str]:
    """Login with existing session cookie, validate it works.

    Returns (cookies_dict, mfp_username).
    Raises ValueError if cookie is invalid.
    """
    logger.info("Attempting cookie-based login")

    try:
        cookies = parse_cookie_input(cookie_input)
        logger.debug(f"Parsed cookies: {list(cookies.keys())}")

        if "__Secure-next-auth.session-token" not in cookies:
            logger.warning("Session token not found in parsed cookies")
            raise ValueError("Invalid cookie: missing session token")

        # Validate the cookie by trying to use it
        session = cffi_requests.Session(impersonate="chrome")
        session.cookies.update(cookies)
        logger.debug("Set up session with provided cookies")

        # Try to fetch home page which redirects to /profile/{username}
        logger.debug("Validating cookie by fetching home page")
        resp = session.get("https://www.myfitnesspal.com/", allow_redirects=True)
        resp.raise_for_status()

        # Extract username from the redirect URL (should end up at /profile/{username})
        final_url = resp.url
        logger.debug(f"Final URL after redirect: {final_url}")

        # Try to extract username from profile URL
        if "/profile/" in str(final_url):
            username = str(final_url).split("/profile/")[-1].split("?")[0].split("#")[0]
            if username:
                logger.info(f"Cookie validated, logged in as: {username}")
                return cookies, username

        # Fallback: try to get username from page content or use "user"
        if "profile" in resp.text.lower():
            logger.info("Cookie validated, session appears valid")
            return cookies, "user"

        raise ValueError("Could not validate cookie - session may be expired")

    except ValueError as e:
        logger.warning(f"Cookie validation failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Cookie login failed: {str(e)}", exc_info=True)
        raise ValueError(f"Cookie validation failed: {str(e)}")

"""Username/password login to MyFitnessPal via NextAuth flow."""

from curl_cffi import requests as cffi_requests


def login_mfp(username: str, password: str) -> tuple[dict[str, str], str]:
    """Login with username/password, extract session cookie.

    Returns (cookies_dict, mfp_username).
    Raises ValueError if login fails.
    """
    session = cffi_requests.Session(impersonate="chrome")

    # Step 1: Get CSRF token
    csrf_resp = session.get("https://www.myfitnesspal.com/api/auth/csrf")
    csrf_resp.raise_for_status()
    csrf_data = csrf_resp.json()
    if "csrfToken" not in csrf_data:
        raise ValueError("Failed to get CSRF token from MFP")
    csrf_token = csrf_data["csrfToken"]

    # Step 2: Login via NextAuth credentials callback
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

    # Step 3: Extract session token from cookies
    cookies = {k: v for k, v in session.cookies.items()}
    if "__Secure-next-auth.session-token" not in cookies:
        raise ValueError("Login failed — check username/password")

    return cookies, username

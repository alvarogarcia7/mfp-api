import re
import uuid
from http.cookiejar import Cookie, CookieJar

import myfitnesspal
from curl_cffi import requests as cffi_requests
from myfitnesspal.exceptions import MyfitnesspalLoginError

RECONNECT_HINT = (
    "MyFitnessPal session expired or not connected. "
    "Re-run login or update your session cookies, then retry."
)


class NotConnectedError(RuntimeError):
    pass


_AUTH_ERROR_PATTERN = re.compile(
    r"\b(401|403|unauthorized|forbidden|csrf|login|log in|logged in|session|token)\b",
    re.IGNORECASE,
)


def is_auth_error(exc: Exception) -> bool:
    if isinstance(exc, (NotConnectedError, MyfitnesspalLoginError)):
        return True
    return bool(_AUTH_ERROR_PATTERN.search(str(exc)))


class CurlCffiClient(myfitnesspal.Client):
    """myfitnesspal.Client over a curl_cffi browser-impersonating session.

    MyFitnessPal sits behind Cloudflare, which fingerprints the upstream
    cloudscraper transport as a bot and 403s even with valid cookies. A real
    Chrome TLS/JA3 fingerprint passes with just the NextAuth session cookie.
    """

    def __init__(
        self,
        cookiejar: CookieJar,
        username: str | None = None,
        impersonate: str | None = None,
    ):
        self._username_override = username
        self._client_instance_id = uuid.uuid4()
        self._request_counter = 0
        self._log_requests_to = None
        self.unit_aware = False
        self.session = cffi_requests.Session(
            impersonate=impersonate or "chrome"
        )
        self.session.cookies.update(cookiejar)
        self._auth_data = self._get_auth_data()
        self._user_metadata = self._get_user_metadata()

    def _get_user_metadata(self):
        """MFP's v2 users endpoint 500s for some accounts; fall back to the
        configured username, which is all the diary URLs need."""
        try:
            meta = super()._get_user_metadata()
            if meta and meta.get("username"):
                return meta
        except Exception:
            pass
        username = self._username_override
        if not username:
            raise MyfitnesspalLoginError(
                "Authenticated, but couldn't read your MyFitnessPal profile. "
                "Set username and retry."
            )
        return {"username": username}


def cookies_to_jar(cookies: dict[str, str]) -> CookieJar:
    jar = CookieJar()
    for name, value in cookies.items():
        jar.set_cookie(
            Cookie(
                version=0,
                name=name,
                value=value,
                port=None,
                port_specified=False,
                domain=".myfitnesspal.com",
                domain_specified=True,
                domain_initial_dot=True,
                path="/",
                path_specified=True,
                secure=True,
                expires=None,
                discard=False,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
        )
    return jar


def build_client(
    cookies: dict[str, str],
    username: str | None = None,
    impersonate: str | None = None,
) -> CurlCffiClient:
    return CurlCffiClient(
        cookies_to_jar(cookies), username=username, impersonate=impersonate
    )

"""Signed session cookies for the admin dashboard.

The cookie holds an expiry time and an HMAC signature. It is HttpOnly
(JavaScript can't read it) and SameSite=Strict (browsers don't send it on
cross-site requests), which protects the admin API from CSRF.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable

COOKIE_NAME = "asa_admin"
SESSION_SECONDS = 12 * 60 * 60


class SessionSigner:
    def __init__(self, secret: bytes, clock: Callable[[], float] = time.time) -> None:
        self._secret = secret
        self._clock = clock

    def issue(self) -> str:
        expires = int(self._clock()) + SESSION_SECONDS
        nonce = secrets.token_urlsafe(12)
        payload = f"{expires}.{nonce}"
        return f"{payload}.{self._sign(payload)}"

    def verify(self, token: str | None) -> bool:
        if not token or token.count(".") != 2:
            return False
        expires, nonce, signature = token.split(".")
        if not hmac.compare_digest(signature, self._sign(f"{expires}.{nonce}")):
            return False
        return expires.isdigit() and int(expires) > self._clock()

    def _sign(self, payload: str) -> str:
        return hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()


def password_matches(given: str, expected: str) -> bool:
    return hmac.compare_digest(given.encode(), expected.encode())

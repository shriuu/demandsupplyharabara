"""Simple PIN sign-in with signed, expiring tokens. Stdlib only, no stored sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections import defaultdict, deque
from collections.abc import Callable

from harabhara.api.settings import ApiSettings, Role, User


class AuthError(Exception):
    pass


class SignInUnavailableError(AuthError):
    """No signing key or PIN directory is configured."""


class TooManyAttemptsError(AuthError):
    pass


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(key: str, body: str) -> str:
    return _b64(hmac.new(key.encode(), body.encode(), hashlib.sha256).digest())


class Authenticator:
    def __init__(self, settings: ApiSettings, clock: Callable[[], float] = time.time) -> None:
        self._s = settings
        self._clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def login(self, pin: str, client: str) -> tuple[str, User]:
        if not self._s.sign_in_ready or self._s.signing_key is None:
            raise SignInUnavailableError
        now = self._clock()
        recent = self._failures[client]
        while recent and now - recent[0] > self._s.login_window_seconds:
            recent.popleft()
        if len(recent) >= self._s.max_failed_logins:
            raise TooManyAttemptsError
        match: User | None = None
        for known, user in self._s.pins.items():  # compare against all, in constant time each
            if hmac.compare_digest(known.encode(), pin.encode()):
                match = user
        if match is None:
            recent.append(now)
            raise AuthError("wrong PIN")
        body = _b64(
            json.dumps(
                {
                    "a": match.actor_id,
                    "r": match.role,
                    "s": match.store_id,
                    "g": match.area_id,
                    "exp": int(now) + self._s.token_ttl_seconds,
                }
            ).encode()
        )
        return f"{body}.{_sign(self._s.signing_key, body)}", match

    def verify(self, token: str) -> User:
        key = self._s.signing_key
        if key is None:
            raise SignInUnavailableError
        try:
            body, sig = token.split(".")
            if not hmac.compare_digest(sig, _sign(key, body)):
                raise AuthError("bad signature")
            claims = json.loads(_unb64(body))
            if claims["exp"] < self._clock():
                raise AuthError("expired")
            role: Role = claims["r"]
            return User(claims["a"], role, claims["s"], claims.get("g"))
        except AuthError:
            raise
        except Exception as exc:
            raise AuthError("bad token") from exc

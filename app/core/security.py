"""Password hashing with bcrypt (NFR-SEC: passwords are never stored in plain text)."""

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings, load_yaml

ALGORITHM = "HS256"
MAX_BCRYPT_BYTES = 72  # bcrypt only uses the first 72 bytes


def hash_password(password: str) -> str:
    data = password.encode("utf-8")
    if len(data) > MAX_BCRYPT_BYTES:
        raise ValueError("Password is too long (max 72 bytes)")
    return bcrypt.hashpw(data, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    data = password.encode("utf-8")
    if len(data) > MAX_BCRYPT_BYTES:
        return False
    return bcrypt.checkpw(data, password_hash.encode("ascii"))


# ---------------------------------------------------------------- API tokens
class TokenError(Exception):
    """The token is missing, forged, malformed or expired."""


def _signing_key() -> str:
    key = get_settings().jwt_secret
    if key in ("", "CHANGE_ME"):
        raise RuntimeError("Set JWT_SECRET in .env to a long random string")
    return key


def create_access_token(user_id: str, role: str, now: datetime | None = None) -> str:
    """A signed login token with a short life (FR-AUTH-02/03)."""
    now = now or datetime.now(UTC)
    minutes = load_yaml("settings.yaml")["security"]["access_token_minutes"]
    claims = {"sub": user_id, "role": role, "iat": now, "exp": now + timedelta(minutes=minutes)}  # fmt: skip
    return jwt.encode(claims, _signing_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _signing_key(), algorithms=[ALGORITHM])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc

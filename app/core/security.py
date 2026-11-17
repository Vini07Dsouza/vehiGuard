"""Password hashing with bcrypt (NFR-SEC: passwords are never stored in plain text)."""

import bcrypt

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

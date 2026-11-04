"""Password hashing and login tokens, independent of FastAPI and the database.

The hash is stored in the encrypted users vault (app/vault.py).
"""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings

# Argon2id with the library's defaults (RFC 9106 / OWASP): slow and memory-hard, so
# guessing passwords from a stolen hash is expensive. Each hash has its own random salt.
_hasher = PasswordHasher()
_ALGORITHM = "HS256"
# Verified against when the login is unknown, so a failed login takes the same
# time whether or not the account exists.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    claims = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes)}
    return jwt.encode(claims, settings.jwt_secret, algorithm=_ALGORITHM)


def read_access_token(token: str) -> int | None:
    """Return the user ID in a valid, unexpired token, otherwise None."""
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM], options={"require": ["exp", "sub"]})
        return int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None

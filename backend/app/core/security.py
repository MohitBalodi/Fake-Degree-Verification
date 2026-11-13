"""Password hashing (argon2) and JWT access/refresh tokens (PyJWT)."""

from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from passlib.context import CryptContext

from app.core.config import settings

TokenType = Literal["access", "refresh"]

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired, or of the wrong type."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def _create_token(user_id: int, role: str, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, role: str, expires_delta: timedelta | None = None) -> str:
    delta = expires_delta or timedelta(minutes=settings.access_token_minutes)
    return _create_token(user_id, role, "access", delta)


def create_refresh_token(user_id: int, role: str, expires_delta: timedelta | None = None) -> str:
    delta = expires_delta or timedelta(days=settings.refresh_token_days)
    return _create_token(user_id, role, "refresh", delta)


def decode_token(token: str, expected_type: TokenType) -> int:
    """Validate a token and return the user id it was issued for."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token_expired", "Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("invalid_token", "Token is invalid.") from exc

    if payload.get("type") != expected_type:
        raise TokenError("invalid_token", f"Expected a {expected_type} token.")
    try:
        return int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise TokenError("invalid_token", "Token is invalid.") from exc

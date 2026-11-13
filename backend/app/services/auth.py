from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.schemas.auth import TokenPair

# Verified against when the email is unknown, so response time doesn't reveal
# which emails exist.
_DUMMY_HASH = hash_password("not-a-real-password")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user


def issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, user.role),
        access_expires_in=settings.access_token_minutes * 60,
    )


def refresh_tokens(db: Session, refresh_token: str) -> TokenPair:
    """Exchange a valid refresh token for a new pair. Raises TokenError."""
    user_id = decode_token(refresh_token, expected_type="refresh")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise TokenError("invalid_token", "User not found or inactive.")
    return issue_tokens(user)

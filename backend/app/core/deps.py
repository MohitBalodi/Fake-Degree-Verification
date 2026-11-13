from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import TokenError, decode_token
from app.models import Role, User

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise _unauthorized("not_authenticated", "Missing bearer token.")
    try:
        user_id = decode_token(credentials.credentials, expected_type="access")
    except TokenError as exc:
        raise _unauthorized(exc.code, exc.message) from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("invalid_token", "User not found or inactive.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: Role) -> Callable[[User], User]:
    """Dependency factory: `Depends(require_role(Role.ADMIN))`."""
    allowed = {r.value for r in roles}

    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "forbidden", "message": "Your role cannot access this resource."},
            )
        return user

    return checker

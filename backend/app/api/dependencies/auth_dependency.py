"""
api/dependencies/auth_dependency.py
──────────────────────────────────
FastAPI dependencies for JWT authentication.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.dependencies.db_dependency import get_internal_db
from app.db.models.user_model import User
from app.services.auth.user_service import get_user_by_username
from app.services.auth.jwt_service import JWTService, TokenExpiredError, TokenInvalidError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_internal_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = JWTService().validate_token(token, expected_type="access")
    except (TokenExpiredError, TokenInvalidError):
        raise credentials_exception

    username: str | None = payload.get("username") or payload.get("sub")
    if not username:
        raise credentials_exception

    user = get_user_by_username(db, username=str(username))
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    # Add logic here if you want to check if user is active/disabled
    return current_user

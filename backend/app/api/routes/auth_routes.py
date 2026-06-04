"""
api/routes/auth_routes.py
────────────────────────
Endpoints for user authentication (signup, login, logout).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies.db_dependency import get_internal_db
from app.api.dependencies.auth_dependency import get_current_user
from app.schemas.auth_schema import UserCreate, UserResponse, Token
from app.schemas.response_schema import SuccessResponse
from app.services.auth.auth_service import (
    authenticate_user,
    create_access_token,
    register_user,
)
from app.db.models.user_model import User

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post(
    "/signup",
    response_model=SuccessResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def signup(
    user_in: UserCreate,
    db: Session = Depends(get_internal_db)
) -> SuccessResponse[UserResponse]:
    """Create a new user account."""
    existing_user = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    from app.services.auth.password_service import WeakPasswordError
    try:
        user = register_user(db, user_in)
        return SuccessResponse(
            message="User registered successfully.",
            data=UserResponse.model_validate(user)
        )
    except WeakPasswordError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post(
    "/login",
    response_model=Token,
    summary="Login to get access token",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_internal_db)
) -> Token:
    """Authenticate a user and return a JWT access token."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return Token(access_token=access_token, token_type="bearer")

@router.post(
    "/logout",
    response_model=SuccessResponse[None],
    summary="Logout user",
)
def logout(current_user: User = Depends(get_current_user)) -> SuccessResponse[None]:
    """
    Log out the current user.
    In JWT-based auth, client just discards the token.
    Server-side can implement token blacklisting if needed.
    """
    return SuccessResponse(message="Logged out successfully.")

@router.get(
    "/me",
    response_model=SuccessResponse[UserResponse],
    summary="Validate session and get current user",
)
def validate_session(current_user: User = Depends(get_current_user)) -> SuccessResponse[UserResponse]:
    """Return the currently authenticated user details."""
    return SuccessResponse(
        message="Session valid.",
        data=UserResponse.model_validate(current_user)
    )

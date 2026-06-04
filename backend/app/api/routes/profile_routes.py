"""
api/routes/profile_routes.py
───────────────────────────
Endpoints for user profile management.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.db_dependency import get_internal_db
from app.api.dependencies.auth_dependency import get_current_user
from app.db.models.user_model import User
from app.schemas.profile_schema import (
    ProfileUpdate,
    ProfileResponse,
    PasswordChangeRequest,
)
from app.schemas.response_schema import SuccessResponse
from app.services.profile.profile_service import (
    update_profile as update_user_profile,
    change_password as change_user_password,
)

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get(
    "",
    response_model=SuccessResponse[ProfileResponse],
    summary="Get logged-in user profile",
)
def read_profile(
    current_user: User = Depends(get_current_user),
) -> SuccessResponse[ProfileResponse]:
    """Retrieve profile details for the authenticated user."""
    return SuccessResponse(
        message="Profile retrieved.",
        data=ProfileResponse.model_validate(current_user),
    )


@router.patch(
    "",
    response_model=SuccessResponse[ProfileResponse],
    summary="Update user profile",
)
def patch_profile(
    profile_update: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_internal_db),
) -> SuccessResponse[ProfileResponse]:
    """Update profile details for the authenticated user."""
    updated_user = update_user_profile(db, current_user.id, profile_update)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return SuccessResponse(
        message="Profile updated successfully.",
        data=ProfileResponse.model_validate(updated_user),
    )


@router.post(
    "/change-password",
    response_model=SuccessResponse[None],
    summary="Change account password",
)
def post_change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_internal_db),
) -> SuccessResponse[None]:
    """Change password after verifying the current one."""
    try:
        change_user_password(
            db,
            current_user.id,
            payload.current_password,
            payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SuccessResponse(message="Password changed successfully.")

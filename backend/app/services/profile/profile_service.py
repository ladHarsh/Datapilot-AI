"""
services/profile/profile_service.py
───────────────────────────────────
Business logic for user profile management.
"""
from __future__ import annotations

from sqlalchemy.orm import Session
from app.db.models.user_model import User
from app.schemas.profile_schema import ProfileUpdate
from app.services.auth.user_service import get_user_by_id
from app.services.auth.password_service import PasswordService, WeakPasswordError

def get_profile(db: Session, user_id: int) -> User | None:
    """Retrieve the user profile by ID."""
    return get_user_by_id(db, user_id)

def update_profile(db: Session, user_id: int, profile_update: ProfileUpdate) -> User | None:
    """Update user profile details."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    update_data = profile_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(user, field):
            setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    return user


def change_password(
    db: Session,
    user_id: int,
    current_password: str,
    new_password: str,
) -> User:
    """Verify current password and set a new hashed password."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    password_service = PasswordService()
    if not password_service.verify(current_password, user.hashed_password):
        raise ValueError("Current password is incorrect.")

    try:
        user.hashed_password = password_service.hash_password(new_password)
    except WeakPasswordError as exc:
        raise ValueError(str(exc)) from exc

    db.commit()
    db.refresh(user)
    return user

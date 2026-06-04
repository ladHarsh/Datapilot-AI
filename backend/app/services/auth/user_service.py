"""
services/auth/user_service.py
────────────────────────────
User management operations.
"""
from __future__ import annotations

from sqlalchemy.orm import Session
from app.db.models.user_model import User
from app.schemas.profile_schema import ProfileUpdate

def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()

def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()

def update_user_profile(db: Session, user_id: int, profile_update: ProfileUpdate) -> User | None:
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

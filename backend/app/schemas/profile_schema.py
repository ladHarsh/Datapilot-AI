"""
schemas/profile_schema.py
────────────────────────
Pydantic schemas for user profile management.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None

class ProfileResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str = "user"
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=100)

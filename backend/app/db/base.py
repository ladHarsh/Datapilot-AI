"""
db/base.py
──────────
SQLAlchemy declarative base shared by all ORM models.
Import ``Base`` from here — never create a second one.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""
    pass

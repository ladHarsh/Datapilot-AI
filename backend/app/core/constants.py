"""
core/constants.py
─────────────────
Application-wide constants.
Never use magic strings/numbers in business logic — reference these instead.
"""
from __future__ import annotations

from typing import FrozenSet, List

# ── SQL Security ───────────────────────────────────────────────────────────────
BLOCKED_SQL_KEYWORDS: FrozenSet[str] = frozenset(
    {
        "DROP",
        "DELETE",
        "UPDATE",
        "INSERT",
        "ALTER",
        "TRUNCATE",
        "CREATE",
        "REPLACE",
        "MERGE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
        "CALL",
        "LOAD",
        "OUTFILE",
        "INTO",
        "RENAME",
        "LOCK",
        "UNLOCK",
        "SET",
        "ATTACH",
        "DETACH",
    }
)

# ── Query Defaults ─────────────────────────────────────────────────────────────
DEFAULT_ROW_LIMIT: int = 1000
DEFAULT_TIMEOUT: int = 30           # seconds

# ── Supported Database Types ──────────────────────────────────────────────────
SUPPORTED_DATABASES: List[str] = ["mysql", "postgresql", "sqlite"]

# ── File Paths ────────────────────────────────────────────────────────────────
EXPORT_FOLDER: str = "exports"
LOG_FOLDER: str = "logs"
UPLOAD_FOLDER: str = "uploads"

# ── Connection Pool ───────────────────────────────────────────────────────────
POOL_SIZE: int = 5
MAX_OVERFLOW: int = 10
POOL_RECYCLE: int = 1800            # seconds (30 min)
POOL_TIMEOUT: int = 30              # seconds

# ── HTTP Status Helpers ───────────────────────────────────────────────────────
HTTP_200_OK: int = 200
HTTP_201_CREATED: int = 201
HTTP_400_BAD_REQUEST: int = 400
HTTP_401_UNAUTHORIZED: int = 401
HTTP_403_FORBIDDEN: int = 403
HTTP_404_NOT_FOUND: int = 404
HTTP_408_TIMEOUT: int = 408
HTTP_422_UNPROCESSABLE: int = 422
HTTP_500_INTERNAL: int = 500

# ── Export Formats ────────────────────────────────────────────────────────────
EXPORT_FORMAT_CSV: str = "csv"
EXPORT_FORMAT_EXCEL: str = "excel"
SUPPORTED_EXPORT_FORMATS: List[str] = [EXPORT_FORMAT_CSV, EXPORT_FORMAT_EXCEL]

# ── API Tags ──────────────────────────────────────────────────────────────────
TAG_DATABASE: str = "Database"
TAG_QUERY: str = "Query"
TAG_EXPORT: str = "Export"
TAG_HISTORY: str = "History"
TAG_HEALTH: str = "Health"
TAG_AUTH: str = "Authentication"
TAG_PROFILE: str = "Profile"

# ── Authentication Constants ──────────────────────────────────────────────────
AUTH_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
PASSWORD_MIN_LENGTH: int = 6
USERNAME_MIN_LENGTH: int = 3

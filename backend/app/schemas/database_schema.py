"""
schemas/database_schema.py
───────────────────────────
Pydantic request/response schemas for database connection operations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.constants import SUPPORTED_DATABASES


# ══════════════════════════════════════════════════════════════════════════════
#  Request schemas
# ══════════════════════════════════════════════════════════════════════════════

class DatabaseConnectRequest(BaseModel):
    """Payload required to open a connection to a target database."""

    host: Optional[str] = Field(
        None,
        max_length=253,
        description="Hostname or IP address of the database server.",
        examples=["localhost", "db.mycompany.com"],
    )
    port: Optional[int] = Field(
        None,
        ge=0,
        lt=65536,
        description="TCP port of the database server (0 for SQLite uploads).",
        examples=[3306, 5432, 0],
    )
    file_path: Optional[str] = Field(
        None,
        description="Absolute path to an uploaded SQLite database file.",
    )
    username: Optional[str] = Field(
        None,
        max_length=128,
        description="Database user account.",
    )
    password: Optional[str] = Field(
        None,
        max_length=256,
        description="Database password (transmitted over HTTPS only).",
    )
    database: Optional[str] = Field(
        None,
        max_length=128,
        description="Name of the target schema / database.",
    )
    database_type: Optional[str] = Field(
        None,
        description=f"Database engine type. Allowed: {SUPPORTED_DATABASES}.",
        examples=["mysql", "postgresql"],
    )

    @field_validator("database_type")
    @classmethod
    def validate_db_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v_lower = v.strip().lower()
        if v_lower not in SUPPORTED_DATABASES:
            raise ValueError(
                f"Unsupported database type '{v}'. "
                f"Supported types: {SUPPORTED_DATABASES}"
            )
        return v_lower

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Host cannot be empty or whitespace.")
        return v

    @model_validator(mode="after")
    def validate_mode(self) -> "DatabaseConnectRequest":
        if self.database_type == "sqlite":
            return self
        if not self.host or self.port is None or not self.username or self.password is None or not self.database:
            raise ValueError(
                "host, port, username, password, and database are required for MySQL/PostgreSQL."
            )
        if self.port == 0:
            raise ValueError("port must be greater than 0 for MySQL/PostgreSQL.")
        return self

    model_config = {"json_schema_extra": {
        "example": {
            "host": "localhost",
            "port": 3306,
            "username": "root",
            "password": "secret",
            "database": "mydb",
            "database_type": "mysql",
        }
    }}


# ══════════════════════════════════════════════════════════════════════════════
#  Column / Table descriptors (returned in schema responses)
# ══════════════════════════════════════════════════════════════════════════════

class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: Optional[str] = None
    autoincrement: bool = False


class ForeignKeyInfo(BaseModel):
    constrained_column: str
    referred_table: str
    referred_column: str


class IndexInfo(BaseModel):
    name: Optional[str] = None
    columns: List[str]
    unique: bool


class TableInfo(BaseModel):
    name: str
    column_count: int
    columns: List[ColumnInfo]
    primary_keys: List[str]
    foreign_keys: List[ForeignKeyInfo]
    indexes: List[IndexInfo]


class DatabaseSchemaResponse(BaseModel):
    database: str
    dialect: str
    table_count: int
    tables: List[TableInfo]
    ai_prompt_schema: Optional[str] = Field(
        None,
        description="Compact text representation of the schema for LLM prompt injection.",
    )


class TableRowStat(BaseModel):
    table_name: str
    row_count: int


class DatabaseStatsResponse(BaseModel):
    database: str
    dialect: str
    table_count: int
    total_rows: int
    active_users: int = Field(
        description="Approximate rows in the first user/customer/employee-like table, if any.",
    )
    tables: List[TableRowStat] = Field(default_factory=list)

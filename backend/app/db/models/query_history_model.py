"""
db/models/query_history_model.py
─────────────────────────────────
ORM model for storing the history of executed queries.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QueryHistory(Base):
    """
    Persists every SQL query executed through the tool.

    Columns
    -------
    id                 : Auto-incrementing primary key.
    connection_key     : Opaque identifier of the database connection used.
    database_type      : "mysql" | "postgresql".
    database_name      : Name of the target database/schema.
    user_query         : Original natural-language question from the user.
    generated_sql      : SQL statement that was executed.
    row_count          : Number of rows returned by the query.
    execution_duration : Wall-clock time in seconds taken to run the query.
    status             : "success" | "error".
    error_message      : Populated when status == "error".
    created_at         : UTC timestamp when the record was inserted.
    """

    __tablename__ = "query_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    query_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    connection_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    database_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_sql: Mapped[str] = mapped_column(Text, nullable=False)

    row_count: Mapped[int] = mapped_column(Integer, default=0)
    execution_duration: Mapped[float] = mapped_column(Float, default=0.0)

    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="queries")

    def __repr__(self) -> str:
        return (
            f"<QueryHistory id={self.id} db={self.database_name} "
            f"status={self.status} rows={self.row_count}>"
        )

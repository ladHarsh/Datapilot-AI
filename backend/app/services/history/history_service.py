"""
Query History Service
======================
Stores executed query history and metadata.
Supports query replay and historical browsing.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, func
from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()


class QueryHistory(Base):
    """SQLAlchemy model for query history records."""
    __tablename__ = "query_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    username = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)

    natural_language_query = Column(Text, nullable=True)    # original NL input
    sql_query = Column(Text, nullable=False)
    normalized_sql = Column(Text, nullable=True)

    execution_status = Column(String(50), default="unknown")  # success / failed / blocked
    error_message = Column(Text, nullable=True)
    row_count = Column(Integer, default=0)
    execution_time_ms = Column(Float, default=0.0)

    risk_level = Column(String(20), nullable=True)
    validation_passed = Column(Boolean, default=False)
    injection_safe = Column(Boolean, default=False)
    complexity_score = Column(Integer, default=0)

    database_name = Column(String(255), nullable=True)
    schema_name = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    executed_at = Column(DateTime(timezone=True), nullable=True)

    client_ip = Column(String(50), nullable=True)
    session_id = Column(String(36), nullable=True)


class HistoryService:
    """
    Manages persistent storage and retrieval of query execution history.

    Supports:
    - Saving executed queries with full metadata
    - Fetching recent query history per user
    - Query replay (re-execute a past query)
    - History search and filtering
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def save_query(
        self,
        sql_query: str,
        execution_status: str,
        row_count: int = 0,
        execution_time_ms: float = 0.0,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        user_role: Optional[str] = None,
        natural_language_query: Optional[str] = None,
        normalized_sql: Optional[str] = None,
        risk_level: Optional[str] = None,
        validation_passed: bool = False,
        injection_safe: bool = False,
        complexity_score: int = 0,
        error_message: Optional[str] = None,
        database_name: Optional[str] = None,
        schema_name: Optional[str] = None,
        client_ip: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Save a query execution record to history.

        Returns:
            The generated query history record ID.
        """
        record = QueryHistory(
            sql_query=sql_query,
            normalized_sql=normalized_sql,
            natural_language_query=natural_language_query,
            execution_status=execution_status,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            user_id=user_id,
            username=username,
            user_role=user_role,
            risk_level=risk_level,
            validation_passed=validation_passed,
            injection_safe=injection_safe,
            complexity_score=complexity_score,
            error_message=error_message,
            database_name=database_name,
            schema_name=schema_name,
            client_ip=client_ip,
            session_id=session_id,
            executed_at=datetime.now(timezone.utc),
        )

        try:
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            logger.info(
                "HistoryService: saved query id=%s status=%s rows=%d time=%.1fms.",
                record.id, execution_status, row_count, execution_time_ms,
            )
            return record.id
        except Exception as exc:
            logger.error("HistoryService: failed to save query — %s", exc)
            self.db.rollback()
            return ""

    def get_user_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve query history for a specific user.

        Args:
            user_id:       The user's ID.
            limit:         Maximum number of records to return.
            offset:        Pagination offset.
            status_filter: Optional filter by execution status.

        Returns:
            List of query history records as dicts.
        """
        try:
            query = (
                self.db.query(QueryHistory)
                .filter(QueryHistory.user_id == user_id)
                .order_by(QueryHistory.created_at.desc())
            )
            if status_filter:
                query = query.filter(QueryHistory.execution_status == status_filter)

            records = query.offset(offset).limit(min(limit, 200)).all()
            return [self._to_dict(r) for r in records]
        except Exception as exc:
            logger.error("HistoryService: failed to fetch user history — %s", exc)
            return []

    def get_query_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single history record by its ID."""
        try:
            record = self.db.query(QueryHistory).filter(QueryHistory.id == record_id).first()
            return self._to_dict(record) if record else None
        except Exception as exc:
            logger.error("HistoryService: failed to fetch record — %s", exc)
            return None

    def get_recent_queries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch the most recent queries across all users (admin use)."""
        try:
            records = (
                self.db.query(QueryHistory)
                .order_by(QueryHistory.created_at.desc())
                .limit(min(limit, 100))
                .all()
            )
            return [self._to_dict(r) for r in records]
        except Exception as exc:
            logger.error("HistoryService: failed to fetch recent queries — %s", exc)
            return []

    def get_replay_sql(self, record_id: str) -> Optional[str]:
        """
        Retrieve the SQL query for replay purposes.

        Returns the original SQL string, or None if not found.
        """
        record = self.db.query(QueryHistory).filter(QueryHistory.id == record_id).first()
        if record:
            logger.info("HistoryService: query replay requested for id=%s.", record_id)
            return record.sql_query
        return None

    def delete_user_history(self, user_id: str) -> int:
        """Delete all history records for a user. Returns deleted count."""
        try:
            count = (
                self.db.query(QueryHistory)
                .filter(QueryHistory.user_id == user_id)
                .delete()
            )
            self.db.commit()
            logger.info("HistoryService: deleted %d records for user_id=%s.", count, user_id)
            return count
        except Exception as exc:
            logger.error("HistoryService: failed to delete history — %s", exc)
            self.db.rollback()
            return 0

    # ── Private helpers ───────────────────────────────────────────────────────

    def _to_dict(self, record: QueryHistory) -> Dict[str, Any]:
        return {
            "id": record.id,
            "user_id": record.user_id,
            "username": record.username,
            "user_role": record.user_role,
            "sql_query": record.sql_query,
            "natural_language_query": record.natural_language_query,
            "execution_status": record.execution_status,
            "row_count": record.row_count,
            "execution_time_ms": record.execution_time_ms,
            "risk_level": record.risk_level,
            "validation_passed": record.validation_passed,
            "injection_safe": record.injection_safe,
            "complexity_score": record.complexity_score,
            "error_message": record.error_message,
            "database_name": record.database_name,
            "schema_name": record.schema_name,
            "client_ip": record.client_ip,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "executed_at": record.executed_at.isoformat() if record.executed_at else None,
        }

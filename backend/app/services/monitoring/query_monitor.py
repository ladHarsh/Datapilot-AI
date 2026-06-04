import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class QueryLogEntry:
    query_id: str
    user_id: str
    sql: str
    status: str  # 'success', 'failed', 'blocked', 'suspicious'
    execution_time_ms: float
    error_message: Optional[str] = None
    timestamp: datetime = datetime.utcnow()
    metadata: Dict[str, Any] = None

class QueryMonitor:
    """
    Monitors and logs SQL query activity for security auditing and analytics.
    """
    
    def __init__(self):
        self._logs: List[QueryLogEntry] = []
        self._suspicious_count = 0
        self._failed_count = 0

    def log_query(
        self, 
        query_id: str, 
        user_id: str, 
        sql: str, 
        status: str, 
        duration_ms: float,
        error: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Record a query execution event."""
        entry = QueryLogEntry(
            query_id=query_id,
            user_id=user_id,
            sql=sql,
            status=status,
            execution_time_ms=duration_ms,
            error_message=error,
            metadata=metadata or {}
        )
        
        self._logs.append(entry)
        
        if status == 'failed':
            self._failed_count += 1
            logger.error(f"QueryMonitor: query {query_id} failed: {error}")
        elif status == 'blocked':
            logger.warning(f"QueryMonitor: query {query_id} blocked by security.")
        elif status == 'suspicious':
            self._suspicious_count += 1
            logger.warning(f"QueryMonitor: suspicious query detected: {query_id}")
            
        # In production, this would persist to a database or ElasticSearch
        logger.info(f"QueryMonitor: logged query {query_id} (status={status}, duration={duration_ms}ms)")

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics of query activity."""
        total = len(self._logs)
        return {
            "total_queries": total,
            "failed_queries": self._failed_count,
            "suspicious_queries": self._suspicious_count,
            "failure_rate": (self._failed_count / total * 100) if total > 0 else 0,
            "avg_duration_ms": sum(l.execution_time_ms for l in self._logs) / total if total > 0 else 0
        }

    def get_recent_logs(self, limit: int = 100) -> List[Dict]:
        """Retrieve the most recent query logs."""
        return [asdict(l) for l in self._logs[-limit:]]

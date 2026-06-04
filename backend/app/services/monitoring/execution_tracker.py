import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class ExecutionMetrics:
    query_id: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    rows_affected: int = 0
    cpu_usage_estimate: float = 0.0
    memory_usage_estimate: float = 0.0
    is_slow_query: bool = False

class ExecutionTracker:
    """
    Tracks real-time query execution performance and detects bottlenecks.
    """
    
    SLOW_QUERY_THRESHOLD_MS = 2000  # 2 seconds

    def __init__(self):
        self._active_executions: Dict[str, ExecutionMetrics] = {}
        self._history: List[ExecutionMetrics] = []

    def start_tracking(self, query_id: str) -> None:
        """Mark the start of a query execution."""
        self._active_executions[query_id] = ExecutionMetrics(
            query_id=query_id,
            start_time=time.time()
        )
        logger.debug(f"ExecutionTracker: started tracking query {query_id}")

    def stop_tracking(self, query_id: str, rows_affected: int = 0) -> Optional[ExecutionMetrics]:
        """Mark the end of a query execution and calculate metrics."""
        metrics = self._active_executions.pop(query_id, None)
        if not metrics:
            return None
            
        metrics.end_time = time.time()
        metrics.duration_ms = (metrics.end_time - metrics.start_time) * 1000
        metrics.rows_affected = rows_affected
        metrics.is_slow_query = metrics.duration_ms > self.SLOW_QUERY_THRESHOLD_MS
        
        self._history.append(metrics)
        
        if metrics.is_slow_query:
            logger.warning(
                f"ExecutionTracker: slow query detected! "
                f"ID={query_id}, Duration={metrics.duration_ms:.2f}ms, Rows={rows_affected}"
            )
        
        return metrics

    def get_performance_summary(self) -> Dict[str, Any]:
        """Generate high-level performance metrics for the dashboard."""
        if not self._history:
            return {"status": "no data"}
            
        total_duration = sum(m.duration_ms for m in self._history)
        slow_queries = [m for m in self._history if m.is_slow_query]
        
        return {
            "total_executed": len(self._history),
            "avg_execution_time_ms": total_duration / len(self._history),
            "slow_query_count": len(slow_queries),
            "slow_query_percentage": (len(slow_queries) / len(self._history)) * 100,
            "max_execution_time_ms": max(m.duration_ms for m in self._history),
        }

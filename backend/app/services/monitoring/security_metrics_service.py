import logging
from collections import Counter
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SecurityMetricsService:
    """
    Aggregates security events into actionable metrics.
    Provides data for security dashboards and health monitoring.
    """

    def __init__(self):
        self._blocked_queries = 0
        self._failed_auths = 0
        self._suspicious_events = 0
        self._violations_by_type = Counter()
        self._start_time = datetime.utcnow()

    def increment_blocked_query(self, violation_type: str = "unknown"):
        self._blocked_queries += 1
        self._violations_by_type[violation_type] += 1

    def increment_failed_auth(self):
        self._failed_auths += 1

    def increment_suspicious_event(self):
        self._suspicious_events += 1

    def get_security_health_score(self) -> float:
        """
        Heuristic score from 0.0 to 100.0 representing platform security health.
        Lower scores indicate higher current attack activity.
        """
        # Simple weighted penalty system
        penalty = (
            (self._blocked_queries * 2) + 
            (self._failed_auths * 5) + 
            (self._suspicious_events * 20)
        )
        return max(0.0, 100.0 - penalty)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Return a snapshot of security activity."""
        return {
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            "health_score": self.get_security_health_score(),
            "totals": {
                "blocked_queries": self._blocked_queries,
                "failed_authentications": self._failed_auths,
                "suspicious_activity_count": self._suspicious_events
            },
            "top_violations": dict(self._violations_by_type.most_common(5))
        }

import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional

# Configure a specific logger for security audits
audit_logger = logging.getLogger("security_audit")
audit_logger.setLevel(logging.INFO)

# In production, this would use a RotatingFileHandler or send to a log aggregator (ELK/Datadog)
# For now, we'll ensure it outputs in a machine-readable JSON format.

class AuditLogger:
    """
    Provides structured logging for all security-critical events.
    Ensures that every access attempt, blocked query, and auth event is traceable.
    """

    def log_event(
        self, 
        event_type: str, 
        user_id: str, 
        status: str, 
        details: Dict[str, Any],
        severity: str = "INFO"
    ):
        """
        Record a security event.
        
        Args:
            event_type: Category (e.g., 'AUTH_LOGIN', 'QUERY_BLOCKED', 'EXPORT_REQUEST')
            user_id:    ID of the user involved.
            status:     'SUCCESS', 'FAILURE', 'BLOCKED', 'ERROR'
            details:    Payload with specific context.
            severity:   Logging level.
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "status": status,
            "severity": severity,
            "details": details
        }
        
        message = json.dumps(log_entry)
        
        if severity == "CRITICAL":
            audit_logger.critical(message)
        elif severity == "ERROR":
            audit_logger.error(message)
        elif severity == "WARNING":
            audit_logger.warning(message)
        else:
            audit_logger.info(message)

    def log_auth_success(self, user_id: str, username: str, ip: str):
        self.log_event("AUTH_LOGIN", user_id, "SUCCESS", {"username": username, "ip": ip})

    def log_auth_failure(self, username: str, ip: str, reason: str):
        self.log_event("AUTH_LOGIN", "anonymous", "FAILURE", {"username": username, "ip": ip, "reason": reason}, "WARNING")

    def log_query_blocked(self, user_id: str, sql: str, reason: str):
        self.log_event("QUERY_SECURITY", user_id, "BLOCKED", {"sql": sql, "reason": reason}, "ERROR")

    def log_suspicious_activity(self, user_id: str, activity_type: str, details: Dict):
        self.log_event("SUSPICIOUS_ACTIVITY", user_id, "DETECTED", {"type": activity_type, **details}, "CRITICAL")

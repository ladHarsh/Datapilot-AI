import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)

class SuspiciousActivityDetector:
    """
    Analyzes patterns of activity to detect potential attacks in real-time.
    Uses sliding windows to track frequency of suspicious events.
    """

    # Thresholds
    MAX_FAILED_LOGINS = 5         # within 15 mins
    MAX_SECURITY_VIOLATIONS = 3   # within 30 mins
    WINDOW_MINUTES = 30

    def __init__(self, audit_logger=None):
        self.audit_logger = audit_logger
        self._failed_logins = defaultdict(list)
        self._security_violations = defaultdict(list)

    def record_failed_login(self, username: str, ip: str):
        """Track failed login attempts to detect brute-force."""
        now = datetime.utcnow()
        self._failed_logins[username].append(now)
        
        # Filter window
        self._failed_logins[username] = [
            t for t in self._failed_logins[username] 
            if now - t < timedelta(minutes=15)
        ]
        
        if len(self._failed_logins[username]) >= self.MAX_FAILED_LOGINS:
            logger.critical(f"SuspiciousActivityDetector: possible brute-force on user '{username}' from IP {ip}")
            if self.audit_logger:
                self.audit_logger.log_suspicious_activity(
                    "anonymous", 
                    "BRUTE_FORCE_ATTEMPT", 
                    {"username": username, "ip": ip, "count": len(self._failed_logins[username])}
                )

    def record_security_violation(self, user_id: str, violation_type: str):
        """Track repeated security violations (e.g., injection attempts)."""
        now = datetime.utcnow()
        self._security_violations[user_id].append((now, violation_type))
        
        # Filter window
        self._security_violations[user_id] = [
            v for v in self._security_violations[user_id] 
            if now - v[0] < timedelta(minutes=self.WINDOW_MINUTES)
        ]
        
        if len(self._security_violations[user_id]) >= self.MAX_SECURITY_VIOLATIONS:
            logger.critical(f"SuspiciousActivityDetector: multiple security violations for user {user_id}")
            if self.audit_logger:
                self.audit_logger.log_suspicious_activity(
                    user_id, 
                    "REPEATED_SECURITY_VIOLATIONS", 
                    {"violations": [v[1] for v in self._security_violations[user_id]]}
                )

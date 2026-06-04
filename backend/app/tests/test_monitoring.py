import pytest
from app.services.monitoring.audit_logger import AuditLogger
from app.services.monitoring.security_metrics_service import SecurityMetricsService

def test_security_metrics_calculation():
    metrics = SecurityMetricsService()
    
    # Initial health
    assert metrics.get_security_health_score() == 100.0
    
    # Record some incidents
    metrics.increment_blocked_query("injection")
    metrics.increment_failed_auth()
    metrics.increment_suspicious_event()
    
    # Health should drop
    health = metrics.get_security_health_score()
    assert health < 100.0
    assert health > 0.0
    
    summary = metrics.get_metrics_summary()
    assert summary["totals"]["blocked_queries"] == 1
    assert "injection" in summary["top_violations"]

def test_audit_logging_flow():
    logger = AuditLogger()
    # This primarily tests that no exceptions are raised during logging
    logger.log_auth_success("123", "testuser", "127.0.0.1")
    logger.log_query_blocked("123", "DROP TABLE users", "DDL_BLOCKED")

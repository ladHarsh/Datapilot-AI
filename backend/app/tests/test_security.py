import pytest
from app.validators.sql_validator import SQLValidator, ValidationStatus
from app.validators.injection_checker import InjectionChecker

def test_sql_validator_allowed():
    validator = SQLValidator()
    
    # SELECT
    res = validator.validate("SELECT * FROM users")
    assert res.status == ValidationStatus.SAFE
    
    # WITH
    res = validator.validate("WITH cte AS (SELECT 1) SELECT * FROM cte")
    assert res.status == ValidationStatus.SAFE
    
    # SHOW
    res = validator.validate("SHOW TABLES")
    assert res.status == ValidationStatus.SAFE

def test_sql_validator_blocked():
    validator = SQLValidator()
    
    # DELETE
    res = validator.validate("DELETE FROM users")
    assert res.status == ValidationStatus.BLOCKED
    
    # DROP
    res = validator.validate("DROP TABLE users")
    assert res.status == ValidationStatus.BLOCKED

def test_injection_checker_tautology():
    checker = InjectionChecker()
    
    # Classic OR 1=1
    res = checker.check("SELECT * FROM users WHERE id = 1 OR 1=1")
    assert res.is_safe is False
    assert "tautology_or_1_eq_1" in res.detected_patterns

def test_injection_checker_union():
    checker = InjectionChecker()
    
    # UNION SELECT
    res = checker.check("SELECT name FROM products UNION SELECT username FROM users")
    assert res.is_safe is False
    assert "union_select" in res.detected_patterns

def test_injection_checker_advanced_evasion():
    checker = InjectionChecker()
    
    # MySQL executable comment evasion
    res = checker.check("SELECT /*!50000 1, */ 2")
    assert res.is_safe is False
    assert "mysql_executable_comment" in res.detected_patterns

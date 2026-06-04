import pytest
from app.validators.injection_checker import InjectionChecker

def test_sql_injection_patterns():
    checker = InjectionChecker()
    
    # 1. Tautologies
    assert checker.check("SELECT * FROM users WHERE '1'='1'").is_safe is False
    assert checker.check("id = 5 OR 1=1").is_safe is False
    
    # 2. Union attacks
    assert checker.check("5 UNION SELECT 1,2,3").is_safe is False
    
    # 3. Stacked queries
    assert checker.check("SELECT 1; DROP TABLE users").is_safe is False
    
    # 4. Comments / Evasion
    assert checker.check("SELECT -- comment").is_safe is False
    assert checker.check("SELECT /*!50000 1 */").is_safe is False
    
    # 5. Time-based / Blind
    assert checker.check("SELECT pg_sleep(5)").is_safe is False
    assert checker.check("WAITFOR DELAY '0:0:5'").is_safe is False

def test_safe_queries():
    checker = InjectionChecker()
    assert checker.check("SELECT name FROM products WHERE id = 10").is_safe is True
    assert checker.check("WITH stats AS (SELECT count(*) FROM sales) SELECT * FROM stats").is_safe is True

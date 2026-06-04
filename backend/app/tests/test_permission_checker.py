import pytest
from app.validators.permission_checker import PermissionChecker

def test_role_based_table_access():
    checker = PermissionChecker()
    
    # 1. Admin should see everything
    res = checker.check("SELECT * FROM users JOIN orders ON users.id = orders.user_id", user_role="admin")
    assert res.is_permitted is True
    
    # 2. Viewer should be blocked from 'users'
    res = checker.check("SELECT * FROM users JOIN orders ON users.id = orders.user_id", user_role="viewer")
    assert res.is_permitted is False
    assert "users" in res.blocked_tables
    
    # 3. Public tables should be fine for everyone
    res = checker.check("SELECT * FROM products JOIN categories ON products.category_id = categories.id", user_role="viewer")
    assert res.is_permitted is True

def test_wildcard_denial():
    checker = PermissionChecker()
    # Attempting to access sensitive internal tables
    res = checker.check("SELECT * FROM credentials", user_role="analyst")
    assert res.is_permitted is False

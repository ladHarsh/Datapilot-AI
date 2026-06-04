"""
test_validators.py
==================
Comprehensive pytest test suite for all validators:
- SQL Validator
- Injection Checker
- Complexity Checker
- Risk Checker
- Schema Validator (with mocked DB engine)
- Permission Checker
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

# ─── Validator imports ────────────────────────────────────────────────────────
from app.validators.sql_validator import SQLValidator, ValidationStatus, validate_sql
from app.validators.injection_checker import InjectionChecker, check_injection
from app.validators.complexity_checker import ComplexityChecker, ComplexityLimits, check_complexity
from app.validators.risk_checker import RiskChecker, RiskLevel, ExecutionRecommendation
from app.validators.schema_validator import SchemaValidator
from app.validators.permission_checker import PermissionChecker, UserRole, check_permission


# ══════════════════════════════════════════════════════════════════════════════
# SQL VALIDATOR TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLValidator:
    """Tests for SQLValidator — ensures only SELECT/WITH are allowed."""

    def setup_method(self):
        self.validator = SQLValidator()

    # ── SAFE queries ──────────────────────────────────────────────────────────

    def test_simple_select_is_safe(self):
        result = self.validator.validate("SELECT * FROM orders LIMIT 100")
        assert result.status == ValidationStatus.SAFE
        assert result.statement_type == "SELECT"
        assert result.is_read_only is True

    def test_select_with_where_is_safe(self):
        result = self.validator.validate(
            "SELECT id, name, email FROM users WHERE active = 1 LIMIT 50"
        )
        assert result.status == ValidationStatus.SAFE

    def test_select_with_join_is_safe(self):
        sql = """
            SELECT o.id, c.name, p.title
            FROM orders o
            INNER JOIN customers c ON o.customer_id = c.id
            INNER JOIN products p ON o.product_id = p.id
            WHERE o.status = 'completed'
            LIMIT 100
        """
        result = self.validator.validate(sql)
        assert result.status == ValidationStatus.SAFE

    def test_cte_with_clause_is_safe(self):
        sql = """
            WITH monthly_sales AS (
                SELECT month, SUM(amount) AS total
                FROM sales
                GROUP BY month
            )
            SELECT * FROM monthly_sales ORDER BY month
        """
        result = self.validator.validate(sql)
        assert result.status == ValidationStatus.SAFE
        assert result.statement_type == "WITH"

    def test_select_with_subquery_is_safe(self):
        sql = "SELECT * FROM (SELECT id, name FROM products WHERE price > 100) AS sub LIMIT 10"
        result = self.validator.validate(sql)
        assert result.status == ValidationStatus.SAFE

    # ── BLOCKED queries ───────────────────────────────────────────────────────

    @pytest.mark.parametrize("dangerous_sql", [
        "DELETE FROM users WHERE id = 1",
        "DELETE FROM orders",
        "DROP TABLE customers",
        "DROP DATABASE production",
        "UPDATE users SET password = 'hacked' WHERE id = 1",
        "INSERT INTO users (name, email) VALUES ('hacker', 'h@x.com')",
        "ALTER TABLE users ADD COLUMN backdoor TEXT",
        "TRUNCATE TABLE orders",
        "CREATE TABLE malicious (id INT)",
        "GRANT ALL PRIVILEGES ON *.* TO 'hacker'@'%'",
        "REVOKE SELECT ON database FROM user",
        "EXEC xp_cmdshell('whoami')",
    ])
    def test_dangerous_sql_is_blocked(self, dangerous_sql):
        result = self.validator.validate(dangerous_sql)
        assert result.status == ValidationStatus.BLOCKED, (
            f"Expected BLOCKED for: {dangerous_sql}"
        )
        assert result.is_read_only is False

    def test_empty_query_is_blocked(self):
        result = self.validator.validate("")
        assert result.status == ValidationStatus.BLOCKED

    def test_blank_whitespace_query_is_blocked(self):
        result = self.validator.validate("   \t\n  ")
        assert result.status == ValidationStatus.BLOCKED

    def test_comment_only_query_is_blocked(self):
        result = self.validator.validate("-- SELECT * FROM users")
        assert result.status == ValidationStatus.BLOCKED

    def test_multiple_statements_blocked(self):
        result = self.validator.validate(
            "SELECT * FROM users; DROP TABLE users"
        )
        assert result.status == ValidationStatus.BLOCKED

    def test_none_input_is_blocked(self):
        result = self.validator.validate(None)
        assert result.status == ValidationStatus.BLOCKED

    def test_validate_sql_convenience_function(self):
        result = validate_sql("SELECT 1")
        assert result["status"] == "safe"

    def test_validation_result_to_dict(self):
        result = self.validator.validate("SELECT id FROM products")
        d = result.to_dict()
        assert "status" in d
        assert "statement_type" in d
        assert "is_read_only" in d
        assert "message" in d


# ══════════════════════════════════════════════════════════════════════════════
# INJECTION CHECKER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestInjectionChecker:
    """Tests for InjectionChecker — validates injection pattern detection."""

    def setup_method(self):
        self.checker = InjectionChecker()

    # ── Clean queries ─────────────────────────────────────────────────────────

    def test_clean_select_is_safe(self):
        result = self.checker.check("SELECT id, name FROM products WHERE price > 50")
        assert result.is_safe is True
        assert result.injection_score == 0
        assert len(result.detected_patterns) == 0

    def test_parameterized_style_query_is_safe(self):
        result = self.checker.check("SELECT * FROM orders WHERE user_id = :user_id LIMIT 100")
        assert result.is_safe is True

    # ── Injection attacks ─────────────────────────────────────────────────────

    @pytest.mark.parametrize("malicious_sql, expected_pattern", [
        ("SELECT * FROM users WHERE id=1 OR 1=1", "tautology_or_1_eq_1"),
        ("SELECT * FROM users UNION SELECT username, password FROM admin", "union_select"),
        ("SELECT * FROM users; DROP TABLE users", "semicolon_injection"),
        ("SELECT * FROM users WHERE name='a'--", "inline_comment"),
        ("SELECT * FROM users WHERE id=1 /* comment */", "block_comment"),
        ("EXEC xp_cmdshell('dir')", "xp_cmdshell"),
        ("SELECT SLEEP(5)", "time_based_sleep"),
        ("SELECT LOAD_FILE('/etc/passwd')", "load_file"),
    ])
    def test_injection_pattern_detected(self, malicious_sql, expected_pattern):
        result = self.checker.check(malicious_sql)
        assert not result.is_safe, f"Expected unsafe for: {malicious_sql}"
        assert expected_pattern in result.detected_patterns, (
            f"Expected pattern '{expected_pattern}' not found in {result.detected_patterns}"
        )

    def test_union_select_detected(self):
        sql = "SELECT name FROM products UNION SELECT username FROM admin_users"
        result = self.checker.check(sql)
        assert not result.is_safe
        assert result.injection_score >= 40

    def test_multiple_statements_injection(self):
        sql = "SELECT 1; DELETE FROM orders WHERE 1=1"
        result = self.checker.check(sql)
        assert not result.is_safe

    def test_xp_cmdshell_scores_maximum(self):
        sql = "EXEC xp_cmdshell('whoami')"
        result = self.checker.check(sql)
        assert result.injection_score == 100   # capped at 100

    def test_empty_query_handled_gracefully(self):
        result = self.checker.check("")
        assert result.is_safe is False
        assert "empty" in result.message.lower()

    def test_sanitization_removes_comments(self):
        sql = "SELECT * FROM users -- this is a comment"
        result = self.checker.check(sql)
        assert "--" not in result.sanitized_query

    def test_sanitization_removes_dangerous_functions(self):
        sql = "SELECT * FROM users WHERE SLEEP(10)"
        result = self.checker.check(sql)
        assert "SLEEP" not in result.sanitized_query

    def test_convenience_function_returns_dict(self):
        result = check_injection("SELECT id FROM users")
        assert isinstance(result, dict)
        assert "is_safe" in result
        assert "injection_score" in result


# ══════════════════════════════════════════════════════════════════════════════
# COMPLEXITY CHECKER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestComplexityChecker:
    """Tests for ComplexityChecker — validates complexity scoring and limits."""

    def setup_method(self):
        self.checker = ComplexityChecker()

    # ── Low complexity ────────────────────────────────────────────────────────

    def test_simple_query_is_low_complexity(self):
        result = self.checker.check("SELECT id, name FROM products WHERE active = 1 LIMIT 10")
        assert result.complexity_level == "low"
        assert result.is_acceptable is True
        assert result.complexity_score < 20

    def test_query_with_two_joins_is_acceptable(self):
        sql = """
            SELECT o.id, c.name, p.title
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN products p ON o.product_id = p.id
            LIMIT 50
        """
        result = self.checker.check(sql)
        assert result.is_acceptable is True
        assert result.join_count == 2

    # ── High complexity ───────────────────────────────────────────────────────

    def test_excessive_joins_detected(self):
        sql = """
            SELECT * FROM a
            JOIN b ON a.id = b.a_id
            JOIN c ON b.id = c.b_id
            JOIN d ON c.id = d.c_id
            JOIN e ON d.id = e.d_id
            JOIN f ON e.id = f.e_id
            JOIN g ON f.id = g.f_id
        """
        result = self.checker.check(sql)
        assert result.join_count > self.checker.limits.MAX_JOINS
        assert len(result.violations) > 0

    def test_deep_subqueries_detected(self):
        sql = """
            SELECT * FROM (
                SELECT * FROM (
                    SELECT * FROM (
                        SELECT * FROM (
                            SELECT id FROM products
                        ) AS l4
                    ) AS l3
                ) AS l2
            ) AS l1
        """
        result = self.checker.check(sql)
        assert result.subquery_depth > self.checker.limits.MAX_SUBQUERY_DEPTH
        assert len(result.violations) > 0

    def test_query_length_limit_enforced(self):
        long_sql = "SELECT " + ", ".join([f"col{i}" for i in range(1000)]) + " FROM huge_table"
        result = self.checker.check(long_sql)
        assert result.query_length > self.checker.limits.MAX_QUERY_LENGTH
        assert any("length" in v.lower() for v in result.violations)

    def test_full_table_scan_detected(self):
        result = self.checker.check("SELECT * FROM orders")
        assert result.has_full_table_scan_risk is True

    def test_select_star_with_limit_no_scan_risk(self):
        result = self.checker.check("SELECT * FROM orders LIMIT 100")
        # With LIMIT, no full scan risk
        assert result.has_full_table_scan_risk is False

    def test_critical_complexity_blocks_execution(self):
        # Construct a query that exceeds all limits
        sql = "SELECT " + ", ".join([f"t{i}.col" for i in range(20)]) + " FROM " + \
              " JOIN ".join([f"table{i} t{i} ON t{i}.id = t{max(0,i-1)}.id" for i in range(15)])
        limits = ComplexityLimits()
        limits.MAX_JOINS = 2
        checker = ComplexityChecker(limits=limits)
        result = checker.check(sql)
        assert not result.is_acceptable

    def test_order_by_without_limit_flagged(self):
        sql = "SELECT id, name FROM products ORDER BY created_at DESC"
        result = self.checker.check(sql)
        assert any("ORDER BY" in w for w in result.warnings)

    def test_convenience_function_returns_dict(self):
        result = check_complexity("SELECT id FROM users LIMIT 10")
        assert isinstance(result, dict)
        assert "complexity_score" in result
        assert "complexity_level" in result


# ══════════════════════════════════════════════════════════════════════════════
# RISK CHECKER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestRiskChecker:
    """Tests for RiskChecker — validates unified risk scoring."""

    def setup_method(self):
        self.checker = RiskChecker()
        self.sql_validator = SQLValidator()
        self.injection_checker = InjectionChecker()
        self.complexity_checker = ComplexityChecker()

    def _run_full_pipeline(self, sql: str):
        validation = self.sql_validator.validate(sql)
        injection = self.injection_checker.check(sql)
        complexity = self.complexity_checker.check(sql)
        return self.checker.analyze(validation, injection, complexity)

    def test_clean_select_is_low_risk(self):
        result = self._run_full_pipeline("SELECT id, name FROM products WHERE active = 1 LIMIT 10")
        assert result.risk_level == RiskLevel.LOW
        assert result.recommendation == ExecutionRecommendation.APPROVE

    def test_dangerous_sql_is_critical_risk(self):
        result = self._run_full_pipeline("DROP TABLE users")
        assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert result.recommendation in (ExecutionRecommendation.BLOCK, ExecutionRecommendation.REJECT)
        assert not result.validation_passed

    def test_injection_attack_is_blocked(self):
        result = self._run_full_pipeline(
            "SELECT * FROM users WHERE id=1 OR 1=1 UNION SELECT username, password FROM admins"
        )
        assert not result.injection_safe
        assert result.recommendation in (ExecutionRecommendation.BLOCK, ExecutionRecommendation.REJECT)

    def test_row_limit_always_applied(self):
        result = self._run_full_pipeline("SELECT * FROM products LIMIT 100")
        assert result.apply_row_limit is True

    def test_risk_result_has_metadata(self):
        result = self._run_full_pipeline("SELECT id FROM users LIMIT 5")
        assert "validation_status" in result.metadata
        assert "injection_score" in result.metadata
        assert "complexity_score" in result.metadata

    def test_result_to_dict(self):
        result = self._run_full_pipeline("SELECT 1")
        d = result.to_dict()
        assert "risk_level" in d
        assert "risk_score" in d
        assert "recommendation" in d
        assert "blocking_reasons" in d
        assert "warnings" in d


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA VALIDATOR TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaValidator:
    """Tests for SchemaValidator — validates table/column references."""

    def setup_method(self):
        # Mock SQLAlchemy engine and inspector
        self.mock_engine = MagicMock()
        self.validator = SchemaValidator(engine=self.mock_engine)

        # Pre-load a fake schema into the cache
        self.validator._schema_cache = {
            "products": {"id", "name", "price", "category_id", "active"},
            "categories": {"id", "name", "description"},
            "orders": {"id", "customer_id", "product_id", "total", "status", "created_at"},
            "customers": {"id", "name", "email", "phone"},
        }

    def test_valid_table_reference_passes(self):
        result = self.validator.validate("SELECT id, name FROM products WHERE active = 1")
        assert result.is_valid is True
        assert "products" in result.validated_tables

    def test_valid_join_references_pass(self):
        sql = "SELECT o.id, c.name FROM orders o JOIN customers c ON o.customer_id = c.id"
        result = self.validator.validate(sql)
        assert result.is_valid is True

    def test_nonexistent_table_fails(self):
        result = self.validator.validate("SELECT * FROM nonexistent_table LIMIT 10")
        assert result.is_valid is False
        assert "nonexistent_table" in result.missing_tables

    def test_nonexistent_column_fails(self):
        sql = "SELECT products.nonexistent_column FROM products"
        result = self.validator.validate(sql)
        assert result.is_valid is False
        assert "nonexistent_column" in result.missing_columns.get("products", [])

    def test_valid_dot_notation_column_passes(self):
        sql = "SELECT products.id, products.name FROM products"
        result = self.validator.validate(sql)
        assert result.is_valid is True

    def test_wildcard_column_is_allowed(self):
        sql = "SELECT products.* FROM products"
        result = self.validator.validate(sql)
        assert result.is_valid is True

    def test_hallucinated_ai_schema_fails(self):
        """Simulate AI hallucinating a non-existent table."""
        result = self.validator.validate(
            "SELECT * FROM ai_generated_table WHERE column_x = 1"
        )
        assert result.is_valid is False
        assert len(result.missing_tables) > 0

    def test_schema_cache_invalidation(self):
        self.validator.invalidate_cache()
        assert self.validator._schema_cache is None


# ══════════════════════════════════════════════════════════════════════════════
# PERMISSION CHECKER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestPermissionChecker:
    """Tests for PermissionChecker — validates RBAC enforcement."""

    def setup_method(self):
        self.checker = PermissionChecker()

    # ── Admin role ────────────────────────────────────────────────────────────

    def test_admin_can_access_any_table(self):
        result = self.checker.check(
            "SELECT * FROM users WHERE id = 1",
            user_role="admin",
        )
        assert result.is_permitted is True
        assert result.applied_row_limit is None   # no limit for admin

    def test_admin_can_use_cte(self):
        result = self.checker.check(
            "WITH cte AS (SELECT * FROM orders) SELECT * FROM cte",
            user_role="admin",
        )
        assert result.is_permitted is True

    # ── Analyst role ──────────────────────────────────────────────────────────

    def test_analyst_can_access_orders_table(self):
        result = self.checker.check(
            "SELECT * FROM orders LIMIT 100",
            user_role="analyst",
        )
        assert result.is_permitted is True
        assert result.applied_row_limit == 10_000

    def test_analyst_blocked_from_users_table(self):
        result = self.checker.check(
            "SELECT * FROM users WHERE id = 1",
            user_role="analyst",
        )
        assert result.is_permitted is False
        assert "users" in result.blocked_tables

    def test_analyst_blocked_from_auth_tokens(self):
        result = self.checker.check(
            "SELECT * FROM auth_tokens WHERE user_id = 1",
            user_role="analyst",
        )
        assert result.is_permitted is False

    def test_analyst_blocked_from_credentials(self):
        result = self.checker.check(
            "SELECT * FROM credentials",
            user_role="analyst",
        )
        assert result.is_permitted is False

    # ── Viewer role ───────────────────────────────────────────────────────────

    def test_viewer_can_access_whitelisted_table(self):
        result = self.checker.check(
            "SELECT id, name FROM products LIMIT 50",
            user_role="viewer",
        )
        assert result.is_permitted is True
        assert result.applied_row_limit == 1_000

    def test_viewer_blocked_from_non_whitelisted_table(self):
        result = self.checker.check(
            "SELECT * FROM audit_logs",
            user_role="viewer",
        )
        assert result.is_permitted is False

    def test_viewer_cannot_use_cte(self):
        result = self.checker.check(
            "WITH cte AS (SELECT * FROM products) SELECT * FROM cte",
            user_role="viewer",
        )
        assert result.is_permitted is False
        assert any("CTE" in v for v in result.violations)

    # ── Invalid role ──────────────────────────────────────────────────────────

    def test_unknown_role_is_rejected(self):
        result = self.checker.check("SELECT 1", user_role="superuser")
        assert result.is_permitted is False
        assert any("unknown role" in v.lower() for v in result.violations)

    def test_convenience_function_returns_dict(self):
        result = check_permission("SELECT id FROM products", "analyst")
        assert isinstance(result, dict)
        assert "is_permitted" in result
        assert "user_role" in result

    def test_get_role_info_admin(self):
        info = self.checker.get_role_info("admin")
        assert info["role"] == "admin"
        assert info["can_access_protected_tables"] is True
        assert info["has_row_limit"] is False

    def test_get_role_info_viewer(self):
        info = self.checker.get_role_info("viewer")
        assert info["role"] == "viewer"
        assert info["has_row_limit"] is True
        assert info["row_limit"] == 1_000

    def test_get_role_info_unknown(self):
        info = self.checker.get_role_info("ghost")
        assert "error" in info


# ══════════════════════════════════════════════════════════════════════════════
# SECURITY PIPELINE INTEGRATION TEST
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurityPipeline:
    """
    End-to-end test: simulates the full security pipeline.
    AI SQL → Validator → Injection → Complexity → Risk → Permission
    """

    def setup_method(self):
        self.sql_validator = SQLValidator()
        self.injection_checker = InjectionChecker()
        self.complexity_checker = ComplexityChecker()
        self.risk_checker = RiskChecker()
        self.permission_checker = PermissionChecker()

    def run_pipeline(self, sql: str, role: str = "analyst") -> dict:
        """Run the complete 5-stage security pipeline."""
        # Stage 1: SQL Validation
        validation = self.sql_validator.validate(sql)

        # Stage 2: Injection Check
        injection = self.injection_checker.check(sql)

        # Stage 3: Complexity Check
        complexity = self.complexity_checker.check(sql)

        # Stage 4: Risk Assessment
        risk = self.risk_checker.analyze(validation, injection, complexity)

        # Stage 5: Permission Check
        permission = self.permission_checker.check(sql, role)

        # Final decision
        can_execute = (
            validation.status.value == "safe"
            and injection.is_safe
            and complexity.is_acceptable
            and risk.recommendation in ("approve", "approve_with_caution")
            and permission.is_permitted
        )

        return {
            "can_execute": can_execute,
            "validation_status": validation.status.value,
            "injection_safe": injection.is_safe,
            "complexity_acceptable": complexity.is_acceptable,
            "risk_level": risk.risk_level.value,
            "recommendation": risk.recommendation.value,
            "permission_granted": permission.is_permitted,
        }

    def test_clean_analyst_query_passes_pipeline(self):
        result = self.run_pipeline(
            "SELECT id, name, price FROM products WHERE active = 1 LIMIT 50",
            role="analyst",
        )
        assert result["can_execute"] is True
        assert result["validation_status"] == "safe"
        assert result["injection_safe"] is True
        assert result["risk_level"] in ("low", "medium")

    def test_drop_table_blocked_at_validation(self):
        result = self.run_pipeline("DROP TABLE users", role="admin")
        assert result["can_execute"] is False
        assert result["validation_status"] == "blocked"

    def test_injection_attack_blocked_at_injection_stage(self):
        result = self.run_pipeline(
            "SELECT * FROM orders WHERE id=1 OR 1=1 UNION SELECT username, password FROM admins",
            role="analyst",
        )
        assert result["can_execute"] is False
        assert result["injection_safe"] is False

    def test_protected_table_blocked_at_permission_stage(self):
        result = self.run_pipeline(
            "SELECT * FROM users WHERE role = 'admin'",
            role="analyst",
        )
        assert result["can_execute"] is False
        assert result["permission_granted"] is False

    def test_viewer_accessing_non_whitelisted_table_blocked(self):
        result = self.run_pipeline(
            "SELECT * FROM audit_logs LIMIT 10",
            role="viewer",
        )
        assert result["can_execute"] is False
        assert result["permission_granted"] is False

    def test_admin_can_run_complex_analytical_query(self):
        sql = """
            WITH revenue AS (
                SELECT c.id, c.name, SUM(o.total) AS total_revenue
                FROM customers c
                JOIN orders o ON c.id = o.customer_id
                WHERE o.status = 'completed'
                GROUP BY c.id, c.name
            )
            SELECT * FROM revenue ORDER BY total_revenue DESC LIMIT 20
        """
        result = self.run_pipeline(sql, role="admin")
        assert result["validation_status"] == "safe"
        assert result["injection_safe"] is True

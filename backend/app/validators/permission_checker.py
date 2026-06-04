"""
Permission & RBAC Checker Module
==================================
Enforces role-based access control on SQL query execution.
Supports three roles: admin, analyst, viewer.
Controls which tables each role can access.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Set, Optional

logger = logging.getLogger(__name__)


# ─── Role Definitions ─────────────────────────────────────────────────────────

class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


# ─── RBAC Policy Configuration ────────────────────────────────────────────────

# Tables that are completely off-limits to all non-admin roles
PROTECTED_TABLES: Set[str] = {
    "users",
    "user_passwords",
    "auth_tokens",
    "sessions",
    "audit_logs",
    "api_keys",
    "credentials",
    "secrets",
    "permissions",
    "roles",
    "role_assignments",
}

# Tables accessible to analyst role
ANALYST_ALLOWED_TABLES: Set[str] = {
    # All tables EXCEPT protected tables; handled dynamically
}

# Tables accessible to viewer role (whitelist — only these tables)
VIEWER_ALLOWED_TABLES: Set[str] = {
    "products",
    "categories",
    "orders",
    "order_items",
    "customers",
    "sales",
    "reports",
    "inventory",
    "regions",
    "departments",
    "employees",
    "projects",
}

# Role-based permissions (what operations each role can perform)
ROLE_PERMISSIONS: Dict[str, Dict] = {
    UserRole.ADMIN: {
        "can_select": True,
        "can_use_cte": True,
        "can_access_protected_tables": True,
        "has_row_limit": False,
        "row_limit": None,
        "allowed_tables": None,          # None = all tables allowed
        "blocked_tables": set(),
    },
    UserRole.ANALYST: {
        "can_select": True,
        "can_use_cte": True,
        "can_access_protected_tables": False,
        "has_row_limit": True,
        "row_limit": 10_000,
        "allowed_tables": None,          # None = all non-protected tables
        "blocked_tables": PROTECTED_TABLES,
    },
    UserRole.VIEWER: {
        "can_select": True,
        "can_use_cte": False,
        "can_access_protected_tables": False,
        "has_row_limit": True,
        "row_limit": 1_000,
        "allowed_tables": VIEWER_ALLOWED_TABLES,   # whitelist
        "blocked_tables": PROTECTED_TABLES,
    },
}


@dataclass
class PermissionCheckResult:
    """Result of RBAC permission check."""
    is_permitted: bool
    user_role: str
    accessed_tables: List[str]
    blocked_tables: List[str]
    violations: List[str]
    applied_row_limit: Optional[int]
    message: str

    def to_dict(self) -> dict:
        return {
            "is_permitted": self.is_permitted,
            "user_role": self.user_role,
            "accessed_tables": self.accessed_tables,
            "blocked_tables": self.blocked_tables,
            "violations": self.violations,
            "applied_row_limit": self.applied_row_limit,
            "message": self.message,
        }


class PermissionChecker:
    """
    Enforces RBAC rules on SQL query execution.

    Rules:
    - admin:   Full access to all tables, no row limit.
    - analyst: Read-only access to non-protected tables, 10,000 row limit.
               Cannot access: users, auth_tokens, credentials, etc.
    - viewer:  Read-only access to whitelisted tables only, 1,000 row limit.
               Cannot use CTEs.
    """

    def __init__(self, custom_role_permissions: Dict = None):
        self.role_permissions = custom_role_permissions or ROLE_PERMISSIONS

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self, sql: str, user_role: str) -> PermissionCheckResult:
        """
        Check if the given role is permitted to execute this SQL query.

        Args:
            sql:       The SQL query string.
            user_role: The role of the authenticated user (admin/analyst/viewer).

        Returns:
            PermissionCheckResult with permission status and restrictions.
        """
        logger.info("PermissionChecker: checking role='%s'.", user_role)

        # Normalize and validate role
        try:
            role = UserRole(user_role.lower())
        except ValueError:
            logger.error("PermissionChecker: unknown role '%s'.", user_role)
            return PermissionCheckResult(
                is_permitted=False,
                user_role=user_role,
                accessed_tables=[],
                blocked_tables=[],
                violations=[f"Unknown role '{user_role}'. Valid roles: admin, analyst, viewer."],
                applied_row_limit=None,
                message=f"Permission denied: unknown role '{user_role}'.",
            )

        perms = self.role_permissions[role]
        violations: List[str] = []

        # Extract tables from query
        accessed_tables = self._extract_tables(sql)
        actually_blocked: List[str] = []

        # ── Check 1: CTE permission ───────────────────────────────────────────
        if not perms["can_use_cte"]:
            if re.search(r"\bWITH\b", sql, re.IGNORECASE):
                violations.append(
                    f"Role '{role.value}' is not permitted to use CTEs (WITH clause)."
                )

        # ── Check 2: Table access ─────────────────────────────────────────────
        for table in accessed_tables:
            t_lower = table.lower()

            # Check against blocked tables (always)
            if t_lower in perms["blocked_tables"]:
                actually_blocked.append(table)
                violations.append(
                    f"Role '{role.value}' is not authorized to access protected table '{table}'."
                )
                logger.warning(
                    "PermissionChecker: role='%s' attempted to access blocked table '%s'.",
                    role.value, table,
                )
                continue

            # Check against whitelist (if applicable)
            if perms["allowed_tables"] is not None:
                if t_lower not in {t.lower() for t in perms["allowed_tables"]}:
                    actually_blocked.append(table)
                    violations.append(
                        f"Role '{role.value}' is not authorized to access table '{table}'. "
                        f"Allowed tables: {', '.join(sorted(perms['allowed_tables']))}."
                    )
                    logger.warning(
                        "PermissionChecker: role='%s' accessed non-whitelisted table '%s'.",
                        role.value, table,
                    )

        is_permitted = len(violations) == 0
        applied_row_limit = perms["row_limit"] if perms["has_row_limit"] else None

        if is_permitted:
            message = (
                f"Role '{role.value}' is authorized to execute this query."
                + (f" Row limit: {applied_row_limit}." if applied_row_limit else "")
            )
        else:
            message = (
                f"Permission denied for role '{role.value}'. "
                f"Violations: {'; '.join(violations)}"
            )

        logger.info(
            "PermissionChecker: is_permitted=%s violations=%d",
            is_permitted, len(violations),
        )

        return PermissionCheckResult(
            is_permitted=is_permitted,
            user_role=role.value,
            accessed_tables=accessed_tables,
            blocked_tables=actually_blocked,
            violations=violations,
            applied_row_limit=applied_row_limit,
            message=message,
        )

    def get_role_info(self, user_role: str) -> dict:
        """Return the permission profile for a given role."""
        try:
            role = UserRole(user_role.lower())
            perms = self.role_permissions[role]
            return {
                "role": role.value,
                "can_select": perms["can_select"],
                "can_use_cte": perms["can_use_cte"],
                "can_access_protected_tables": perms["can_access_protected_tables"],
                "has_row_limit": perms["has_row_limit"],
                "row_limit": perms["row_limit"],
                "blocked_tables": list(perms["blocked_tables"]),
                "allowed_tables": (
                    list(perms["allowed_tables"])
                    if perms["allowed_tables"] is not None
                    else "all (non-protected)"
                ),
            }
        except ValueError:
            return {"error": f"Unknown role '{user_role}'."}

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_tables(self, sql: str) -> List[str]:
        """Extract table names from SQL using FROM/JOIN patterns."""
        patterns = [
            r"\bFROM\s+([`\"\[]?[\w]+[`\"\]]?(?:\s*,\s*[`\"\[]?[\w]+[`\"\]]?)*)",
            r"\b(?:INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+OUTER\s+|CROSS\s+)?JOIN\s+([`\"\[]?[\w]+[`\"\]]?)",
        ]

        tables: Set[str] = set()
        SQL_KEYWORDS = {
            "select", "from", "where", "join", "inner", "outer", "left", "right",
            "full", "cross", "on", "as", "and", "or", "with", "group", "having",
            "order", "limit", "offset", "union", "distinct", "case", "when",
            "then", "else", "end", "null", "true", "false",
        }

        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                for table in match.split(","):
                    cleaned = re.sub(r"[`\"\[\]\s]", "", table).strip()
                    parts = cleaned.split()
                    if parts:
                        name = parts[0].strip()
                        if name and name.lower() not in SQL_KEYWORDS:
                            tables.add(name)

        # Remove subquery aliases
        subquery_aliases = re.findall(r"\)\s+(?:AS\s+)?(\w+)", sql, re.IGNORECASE)
        tables -= set(subquery_aliases)

        return list(tables)


# ── Module-level convenience function ─────────────────────────────────────────

def check_permission(sql: str, user_role: str) -> dict:
    """
    Convenience function for permission checking.

    Args:
        sql:       SQL query string.
        user_role: User role string (admin/analyst/viewer).

    Returns:
        dict with permission check result.
    """
    checker = PermissionChecker()
    return checker.check(sql, user_role).to_dict()

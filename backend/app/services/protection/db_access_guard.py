import logging
from typing import List, Set
from app.validators.permission_checker import PROTECTED_TABLES

logger = logging.getLogger(__name__)

class DBAccessError(Exception):
    """Raised when an unauthorized database access attempt is detected."""
    pass

class DBAccessGuard:
    """
    Enforces low-level database access policies.
    Ensures that the connection is used strictly for read-only analytical purposes.
    """

    # Operations that are strictly forbidden regardless of role
    FORBIDDEN_OPERATIONS = {
        "DROP", "TRUNCATE", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
        "GRANT", "REVOKE", "SHUTDOWN", "REPLACE"
    }

    def __init__(self, readonly: bool = True):
        self.readonly = readonly

    def validate_operation(self, sql_type: str) -> None:
        """
        Ensure the SQL operation type is permitted.
        """
        if self.readonly and sql_type.upper() in self.FORBIDDEN_OPERATIONS:
            logger.error(f"DBAccessGuard: blocked forbidden operation '{sql_type}' in read-only mode.")
            raise DBAccessError(f"Database operation '{sql_type}' is not allowed. Only read-only queries are permitted.")

    def check_table_access(self, tables: List[str], user_role: str) -> None:
        """
        Final check to ensure no protected tables are accessed by unauthorized roles.
        """
        if user_role.lower() == "admin":
            return

        for table in tables:
            if table.lower() in PROTECTED_TABLES:
                logger.error(f"DBAccessGuard: blocked access to protected table '{table}' for role '{user_role}'.")
                raise DBAccessError(f"Access to protected table '{table}' is strictly prohibited.")
                
        logger.debug(f"DBAccessGuard: table access validated for role '{user_role}'.")

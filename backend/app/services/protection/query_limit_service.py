import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class QueryLimitError(Exception):
    """Raised when query results exceed safety limits."""
    pass

class QueryLimitService:
    """
    Enforces row and data size limits on query results.
    Protects both backend memory and frontend responsiveness.
    """

    MAX_ROWS = 100_000
    SAFE_ROWS = 10_000
    MAX_CELL_SIZE_BYTES = 1024 * 1024  # 1MB per cell

    def __init__(self, default_row_limit: int = SAFE_ROWS):
        self.default_row_limit = default_row_limit

    def apply_row_limit(self, sql: str, limit: int = None) -> str:
        """
        Append or replace LIMIT clause in the SQL query.
        """
        final_limit = min(limit or self.default_row_limit, self.MAX_ROWS)
        
        # Basic regex to handle existing LIMIT
        import re
        if re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
            sql = re.sub(r"\bLIMIT\s+\d+", f"LIMIT {final_limit}", sql, flags=re.IGNORECASE)
        else:
            sql = f"{sql.rstrip().rstrip(';')} LIMIT {final_limit}"
            
        logger.info(f"QueryLimitService: applied limit of {final_limit} rows.")
        return sql

    def validate_result_size(self, rows: List[Any]) -> None:
        """
        Check if the returned result set is too large to handle.
        """
        row_count = len(rows)
        if row_count > self.MAX_ROWS:
            logger.error(f"QueryLimitService: result set too large ({row_count} rows).")
            raise QueryLimitError(f"Result set too large ({row_count} rows). Maximum allowed is {self.MAX_ROWS}.")
            
        # Optional: check total memory size of rows
        # For now, we trust the row count limit.
        logger.debug(f"QueryLimitService: validated result size ({row_count} rows).")

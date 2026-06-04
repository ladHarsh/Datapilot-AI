import logging
import re

logger = logging.getLogger(__name__)

class QuerySanitizer:
    """
    Cleans and normalizes SQL queries before they are sent to the database.
    Prevents evasion techniques like obfuscated comments or hidden control characters.
    """

    def sanitize(self, sql: str) -> str:
        if not sql:
            return ""

        # 1. Remove null bytes
        sql = sql.replace("\0", "")

        # 2. Remove multiple semicolons (prevent stacked queries if not intended)
        sql = re.sub(r";\s*;", ";", sql)

        # 3. Normalize whitespace
        sql = re.sub(r"\s+", " ", sql).strip()

        # 4. Strip leading/trailing comments that might hide the real query
        sql = re.sub(r"^/\*.*?\*/", "", sql)
        sql = re.sub(r"--.*$", "", sql)

        logger.debug("QuerySanitizer: SQL sanitized and normalized.")
        return sql

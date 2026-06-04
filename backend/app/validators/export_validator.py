import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

class ExportValidator:
    """
    Validates parameters specific to data exports.
    Prevents path traversal, dangerous filenames, and invalid delimiters.
    """

    def validate_filename(self, filename: str) -> bool:
        if not filename:
            return False
            
        # No path traversal characters
        if ".." in filename or "/" in filename or "\\" in filename:
            logger.warning(f"ExportValidator: blocked dangerous filename '{filename}'")
            return False
            
        # Basic alphanumeric + dot/dash/underscore
        if not re.match(r"^[\w\-. ]+$", filename):
            return False
            
        return len(filename) < 255

    def validate_csv_params(self, delimiter: str):
        allowed = [",", ";", "|", "\t"]
        if delimiter not in allowed:
            logger.error(f"ExportValidator: invalid CSV delimiter '{delimiter}'")
            return False
        return True

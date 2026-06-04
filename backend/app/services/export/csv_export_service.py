"""
CSV Export Service
==================
Securely exports SQL query results to CSV format.
Validates export size limits and handles encoding safely.
"""

import csv
import io
import logging
from typing import List, Dict, Any, Optional

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# ─── Export limits ────────────────────────────────────────────────────────────
MAX_EXPORT_ROWS = 50_000
MAX_EXPORT_SIZE_BYTES = 50 * 1024 * 1024   # 50 MB


class CSVExportService:
    """
    Converts query result rows into a downloadable CSV file.
    Enforces row and size limits to prevent memory overload.
    """

    def export(
        self,
        rows: List[Dict[str, Any]],
        user_role: str,
        filename: str = "query_results.csv",
        delimiter: str = ",",
        max_rows: int = MAX_EXPORT_ROWS,
    ) -> StreamingResponse:
        """
        Generate a CSV StreamingResponse from query result rows.

        Args:
            rows:      List of dicts representing query result rows.
            user_role: Role of the user requesting the export.
            filename:  Desired download filename.
            delimiter: CSV delimiter character.
            max_rows:  Maximum rows to export (overrides global limit if smaller).

        Returns:
            FastAPI StreamingResponse with CSV content.

        Raises:
            ValueError: If rows exceed limits or data is invalid.
            PermissionError: If user role is not authorized.
        """
        logger.info("CSVExportService: export requested by role='%s'.", user_role)

        # 1. Permission check
        if user_role.lower() not in ["admin", "analyst"]:
            logger.warning("CSVExportService: unauthorized export attempt by role='%s'.", user_role)
            raise PermissionError(f"Role '{user_role}' is not authorized to export data. Only admins and analysts can export.")

        logger.info("CSVExportService: exporting %d rows.", len(rows))

        if not rows:
            logger.warning("CSVExportService: empty result set.")
            rows = []

        # Apply row limit
        effective_limit = min(max_rows, MAX_EXPORT_ROWS)
        truncated = False
        if len(rows) > effective_limit:
            logger.warning(
                "CSVExportService: truncating from %d to %d rows.",
                len(rows), effective_limit,
            )
            rows = rows[:effective_limit]
            truncated = True

        # Generate CSV in memory
        output = io.StringIO()
        if rows:
            headers = list(rows[0].keys())
            writer = csv.DictWriter(
                output,
                fieldnames=headers,
                delimiter=delimiter,
                quoting=csv.QUOTE_ALL,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)

        # Size guard
        content = output.getvalue()
        size_bytes = len(content.encode("utf-8"))
        if size_bytes > MAX_EXPORT_SIZE_BYTES:
            raise ValueError(
                f"Export size ({size_bytes / 1024 / 1024:.1f} MB) exceeds "
                f"the maximum allowed ({MAX_EXPORT_SIZE_BYTES / 1024 / 1024:.0f} MB)."
            )

        logger.info(
            "CSVExportService: generated %.2f KB%s.",
            size_bytes / 1024,
            " (truncated)" if truncated else "",
        )

        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)

        def iter_content():
            yield content.encode("utf-8-sig")   # BOM for Excel compatibility

        return StreamingResponse(
            iter_content(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "X-Row-Count": str(len(rows)),
                "X-Truncated": str(truncated).lower(),
                "X-Export-Size-Bytes": str(size_bytes),
            },
        )

    def to_csv_string(
        self,
        rows: List[Dict[str, Any]],
        delimiter: str = ",",
        max_rows: int = MAX_EXPORT_ROWS,
    ) -> str:
        """
        Return CSV as a plain string (useful for embedding in responses or testing).
        """
        if not rows:
            return ""

        effective_limit = min(max_rows, MAX_EXPORT_ROWS)
        rows = rows[:effective_limit]

        output = io.StringIO()
        headers = list(rows[0].keys())
        writer = csv.DictWriter(
            output, fieldnames=headers, delimiter=delimiter,
            quoting=csv.QUOTE_ALL, extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Strip path traversal and dangerous characters from filename."""
        import re
        safe = re.sub(r"[^\w\-. ]", "_", filename)
        return safe[:200]   # max length

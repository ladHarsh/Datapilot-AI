"""
PDF Export Service
==================
Generates professionally formatted PDF reports from SQL query results.
Uses ReportLab for PDF generation with tables, metadata, and charts.
"""

import io
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# ─── Export limits ────────────────────────────────────────────────────────────
MAX_EXPORT_ROWS = 10_000
MAX_EXPORT_SIZE_BYTES = 50 * 1024 * 1024   # 50 MB


class PDFExportService:
    """
    Generates PDF reports from SQL query results using ReportLab.
    Supports professional table formatting, metadata headers, and summary stats.
    """

    # Brand colors
    PRIMARY_COLOR = (0.12, 0.22, 0.39)      # Dark navy
    ACCENT_COLOR = (0.20, 0.53, 0.82)       # Blue
    ALT_ROW_COLOR = (0.93, 0.95, 0.98)      # Light blue-gray
    TEXT_COLOR = (0.15, 0.15, 0.15)

    def export(
        self,
        rows: List[Dict[str, Any]],
        user_role: str,
        filename: str = "query_results.pdf",
        title: str = "Query Results Report",
        subtitle: str = "",
        generated_by: str = "SQL Analytics Platform",
        max_rows: int = MAX_EXPORT_ROWS,
        include_summary: bool = True,
    ) -> StreamingResponse:
        """
        Generate a PDF report from query result rows.

        Args:
            rows:          Query result rows as list of dicts.
            user_role:     Role of the user requesting the export.
            filename:      Output filename.
            title:         Report title shown in header.
            subtitle:      Optional subtitle or query description.
            generated_by:  System/user attribution.
            max_rows:      Maximum rows to include.
            include_summary: Add a summary stats section.

        Returns:
            FastAPI StreamingResponse with PDF content.
        """
        logger.info("PDFExportService: export requested by role='%s'.", user_role)

        # 1. Permission check
        if user_role.lower() not in ["admin", "analyst"]:
            logger.warning("PDFExportService: unauthorized export attempt by role='%s'.", user_role)
            raise PermissionError(f"Role '{user_role}' is not authorized to export data. Only admins and analysts can export.")

        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm, mm
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, HRFlowable, KeepTogether,
            )
            from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        except ImportError:
            raise ImportError(
                "reportlab is required for PDF export. "
                "Install it with: pip install reportlab"
            )

        logger.info("PDFExportService: exporting %d rows.", len(rows))

        effective_limit = min(max_rows, MAX_EXPORT_ROWS)
        truncated = False
        if len(rows) > effective_limit:
            rows = rows[:effective_limit]
            truncated = True
            logger.warning("PDFExportService: truncated to %d rows.", effective_limit)

        buffer = io.BytesIO()

        # Use landscape for wide result sets
        headers = list(rows[0].keys()) if rows else []
        page_size = landscape(A4) if len(headers) > 6 else A4

        doc = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title=title,
            author=generated_by,
        )

        styles = getSampleStyleSheet()
        primary_rgb = colors.Color(*self.PRIMARY_COLOR)
        accent_rgb = colors.Color(*self.ACCENT_COLOR)
        alt_row_rgb = colors.Color(*self.ALT_ROW_COLOR)

        # Custom styles
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontSize=20,
            fontName="Helvetica-Bold",
            textColor=primary_rgb,
            spaceAfter=6,
            alignment=TA_LEFT,
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            fontName="Helvetica",
            textColor=colors.grey,
            spaceAfter=4,
        )
        meta_style = ParagraphStyle(
            "MetaInfo",
            parent=styles["Normal"],
            fontSize=8,
            fontName="Helvetica",
            textColor=colors.grey,
        )
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=12,
            fontName="Helvetica-Bold",
            textColor=accent_rgb,
            spaceBefore=12,
            spaceAfter=6,
        )

        story = []

        # ── Header ───────────────────────────────────────────────────────────
        story.append(Paragraph(title, title_style))
        if subtitle:
            story.append(Paragraph(subtitle, subtitle_style))
        story.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} &nbsp;|&nbsp; "
            f"By: {generated_by} &nbsp;|&nbsp; Rows: {len(rows):,}",
            meta_style,
        ))
        story.append(HRFlowable(width="100%", thickness=1.5, color=accent_rgb, spaceAfter=12))

        # ── Truncation notice ─────────────────────────────────────────────────
        if truncated:
            notice_style = ParagraphStyle(
                "TruncNotice",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.orange,
                spaceBefore=4, spaceAfter=8,
            )
            story.append(Paragraph(
                f"⚠ Note: Results truncated to {effective_limit:,} rows. "
                "Export the full dataset using CSV or Excel format.",
                notice_style,
            ))

        # ── Summary stats ─────────────────────────────────────────────────────
        if include_summary and rows:
            story.append(Paragraph("Export Summary", section_style))
            summary_data = [
                ["Metric", "Value"],
                ["Total Rows Exported", f"{len(rows):,}"],
                ["Total Columns", str(len(headers))],
                ["Column Names", ", ".join(headers[:10]) + ("..." if len(headers) > 10 else "")],
                ["Export Timestamp", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")],
                ["Report Truncated", "Yes" if truncated else "No"],
            ]
            summary_table = Table(summary_data, colWidths=[5 * cm, None])
            summary_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), primary_rgb),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, alt_row_rgb]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 0.5 * cm))

        # ── Data table ────────────────────────────────────────────────────────
        if rows:
            story.append(Paragraph("Data Results", section_style))

            # Build table data
            table_data = [headers]
            for row in rows:
                table_data.append([
                    self._format_cell(row.get(h, "")) for h in headers
                ])

            # Dynamic column width
            page_width = page_size[0] - 3 * cm
            col_width = page_width / len(headers) if headers else page_width

            data_table = Table(table_data, colWidths=[col_width] * len(headers), repeatRows=1)
            data_table.setStyle(TableStyle([
                # Header row
                ("BACKGROUND", (0, 0), (-1, 0), primary_rgb),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                # Data rows
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, alt_row_rgb]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("WORDWRAP", (0, 0), (-1, -1), True),
            ]))
            story.append(data_table)
        else:
            story.append(Paragraph("No data available for this query.", styles["Normal"]))

        # Build PDF
        doc.build(story, onFirstPage=self._add_page_footer, onLaterPages=self._add_page_footer)

        content = buffer.getvalue()

        if len(content) > MAX_EXPORT_SIZE_BYTES:
            raise ValueError(
                f"PDF export size ({len(content) / 1024 / 1024:.1f} MB) "
                f"exceeds the maximum allowed ({MAX_EXPORT_SIZE_BYTES / 1024 / 1024:.0f} MB)."
            )

        logger.info("PDFExportService: generated %.2f KB.", len(content) / 1024)
        safe_filename = self._sanitize_filename(filename)

        return StreamingResponse(
            iter([content]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "X-Row-Count": str(len(rows)),
                "X-Truncated": str(truncated).lower(),
                "X-Export-Size-Bytes": str(len(content)),
            },
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _format_cell(self, value: Any) -> str:
        """Format a cell value for safe PDF rendering."""
        if value is None:
            return "NULL"
        text = str(value)
        # Truncate very long cell values
        if len(text) > 200:
            text = text[:197] + "..."
        return text

    def _add_page_footer(self, canvas, doc):
        """Add page number and branding to each page."""
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillGray(0.5)
        page_num = canvas.getPageNumber()
        canvas.drawRightString(
            doc.pagesize[0] - 1.5 * 28.35,
            0.8 * 28.35,
            f"Page {page_num}",
        )
        canvas.drawString(
            1.5 * 28.35,
            0.8 * 28.35,
            "SQL Analytics Platform — Confidential",
        )
        canvas.restoreState()

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        import re
        safe = re.sub(r"[^\w\-. ]", "_", filename)
        return safe[:200]

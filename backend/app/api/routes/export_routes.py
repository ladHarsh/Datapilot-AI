"""
api/routes/export_routes.py
────────────────────────────
Endpoints for exporting query results to CSV or Excel.

POST /export/csv   — Stream a CSV file.
POST /export/excel — Stream an Excel (.xlsx) file.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.constants import TAG_EXPORT
from app.core.logger import app_logger

router = APIRouter(prefix="/export", tags=[TAG_EXPORT])

EXPORT_DIR = Path(settings.EXPORT_FOLDER)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


# ── Request body ──────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    """Payload containing the query result to be exported."""

    columns: List[str] = Field(..., description="Ordered column names.")
    rows: List[Dict[str, Any]] = Field(..., description="List of row dicts.")
    filename: str = Field(
        default="query_result",
        max_length=128,
        description="Base filename without extension.",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_dataframe(payload: ExportRequest) -> pd.DataFrame:
    """Construct a DataFrame from the export payload."""
    if not payload.rows:
        return pd.DataFrame(columns=payload.columns)
    df = pd.DataFrame(payload.rows, columns=payload.columns)
    return df


def _safe_filename(base: str, ext: str) -> str:
    """Return a timestamped, filesystem-safe filename."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_base = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in base)
    return f"{safe_base}_{timestamp}.{ext}"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/csv",
    summary="Export query result as CSV",
    description="Converts a query result payload into a downloadable CSV file.",
    response_class=StreamingResponse,
)
def export_csv(payload: ExportRequest) -> StreamingResponse:
    """Stream query results as a CSV file."""
    app_logger.info(
        "CSV export requested — rows=%d filename=%s",
        len(payload.rows), payload.filename,
    )

    df = _build_dataframe(payload)

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data to export.",
        )

    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    fname = _safe_filename(payload.filename, "csv")
    app_logger.info("Streaming CSV: %s (%d rows)", fname, len(df))

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.post(
    "/excel",
    summary="Export query result as Excel",
    description="Converts a query result payload into a downloadable .xlsx file.",
    response_class=StreamingResponse,
)
def export_excel(payload: ExportRequest) -> StreamingResponse:
    """Stream query results as an Excel workbook."""
    app_logger.info(
        "Excel export requested — rows=%d filename=%s",
        len(payload.rows), payload.filename,
    )

    df = _build_dataframe(payload)

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data to export.",
        )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Query Result")
    buffer.seek(0)

    fname = _safe_filename(payload.filename, "xlsx")
    app_logger.info("Streaming Excel: %s (%d rows)", fname, len(df))

    return StreamingResponse(
        iter([buffer.read()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )

import logging
from typing import List, Dict, Any, Optional
from app.services.export.csv_export_service import CSVExportService
from app.services.export.excel_export_service import ExcelExportService
from app.services.export.pdf_export_service import PDFExportService

logger = logging.getLogger(__name__)

class ExportManager:
    """
    Unified manager for all data export operations.
    Determines the correct service to use based on requested format.
    """

    def __init__(self):
        self.csv_service = CSVExportService()
        self.excel_service = ExcelExportService()
        self.pdf_service = PDFExportService()

    def handle_export(
        self, 
        format: str, 
        rows: List[Dict[str, Any]], 
        user_role: str,
        **kwargs
    ):
        """
        Main entry point for triggering an export.
        """
        fmt = format.lower()
        logger.info(f"ExportManager: processing {fmt} export for role {user_role}")
        
        if fmt == "csv":
            return self.csv_service.export(rows, user_role=user_role, **kwargs)
        elif fmt == "excel":
            return self.excel_service.export(rows, user_role=user_role, **kwargs)
        elif fmt == "pdf":
            return self.pdf_service.export(rows, user_role=user_role, **kwargs)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

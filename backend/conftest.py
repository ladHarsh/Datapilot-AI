"""
conftest.py — pytest configuration and shared fixtures
"""
# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import MagicMock

from app.validators.sql_validator import SQLValidator
from app.validators.injection_checker import InjectionChecker
from app.validators.complexity_checker import ComplexityChecker
from app.validators.risk_checker import RiskChecker
from app.validators.schema_validator import SchemaValidator
from app.validators.permission_checker import PermissionChecker
from app.services.export.csv_export_service import CSVExportService
from app.services.export.excel_export_service import ExcelExportService
from app.services.export.pdf_export_service import PDFExportService


@pytest.fixture(scope="session")
def sql_validator():
    return SQLValidator()


@pytest.fixture(scope="session")
def injection_checker():
    return InjectionChecker()


@pytest.fixture(scope="session")
def complexity_checker():
    return ComplexityChecker()


@pytest.fixture(scope="session")
def risk_checker():
    return RiskChecker()


@pytest.fixture(scope="function")
def schema_validator():
    mock_engine = MagicMock()
    validator = SchemaValidator(engine=mock_engine)
    validator._schema_cache = {
        "products": {"id", "name", "price", "category_id", "active"},
        "categories": {"id", "name", "description"},
        "orders": {"id", "customer_id", "product_id", "total", "status", "created_at"},
        "customers": {"id", "name", "email", "phone"},
        "sales": {"id", "product_id", "amount", "month", "year"},
        "employees": {"id", "name", "department_id", "salary"},
        "departments": {"id", "name", "budget"},
    }
    return validator


@pytest.fixture(scope="session")
def permission_checker():
    return PermissionChecker()


@pytest.fixture(scope="session")
def csv_service():
    return CSVExportService()


@pytest.fixture(scope="session")
def excel_service():
    return ExcelExportService()


@pytest.fixture(scope="session")
def pdf_service():
    return PDFExportService()


@pytest.fixture
def sample_rows():
    return [
        {"id": 1, "name": "Product A", "price": 99.99, "category": "Electronics"},
        {"id": 2, "name": "Product B", "price": 49.50, "category": "Clothing"},
        {"id": 3, "name": "Product C", "price": 199.00, "category": "Electronics"},
    ]

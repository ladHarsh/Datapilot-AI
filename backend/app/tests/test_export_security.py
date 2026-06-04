import pytest
from app.services.export.csv_export_service import CSVExportService

def test_export_permission_denied():
    service = CSVExportService()
    rows = [{"id": 1, "data": "test"}]
    
    # Viewer should be denied
    with pytest.raises(PermissionError) as exc:
        service.export(rows, user_role="viewer")
    assert "not authorized to export" in str(exc.value)

def test_export_permission_granted():
    service = CSVExportService()
    rows = [{"id": 1, "data": "test"}]
    
    # Admin and Analyst should be allowed
    response = service.export(rows, user_role="admin")
    assert response.status_code == 200
    
    response = service.export(rows, user_role="analyst")
    assert response.status_code == 200

def test_export_size_limit():
    service = CSVExportService()
    # Mocking massive data
    rows = [{"col": "data"}] * 60_000 
    
    # Should trigger row limit (truncation) or error if size too big
    # Actually CSV service truncates by default in my implementation.
    response = service.export(rows, user_role="admin")
    assert response.headers["X-Truncated"] == "true"

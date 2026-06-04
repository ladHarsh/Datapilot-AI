"""
tests/test_api.py
──────────────────
Integration tests for all REST API endpoints using TestClient.

Run with:
    cd backend
    pytest app/tests/test_api.py -v
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.api.dependencies.auth_dependency import get_current_user
from app.db.models.user_model import User

TEST_DB_URL = "sqlite:///./test_sql_tool.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_current_user():
    return User(
        id=1,
        username="testuser",
        email="testuser@example.com",
        hashed_password="hashed_password",
        role="admin"
    )


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    if not db.query(User).filter_by(id=1).first():
        user = User(
            id=1,
            username="testuser",
            email="testuser@example.com",
            hashed_password="hashed_password",
            role="admin"
        )
        db.add(user)
        db.commit()
    db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── Health ────────────────────────────────────────────────────────────────────
class TestHealth:
    def test_health_200(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_root_200(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "docs" in r.json()


# ── Database routes ───────────────────────────────────────────────────────────
class TestDatabaseConnect:
    URL = "/api/v1/database/connect"

    def test_missing_fields_422(self, client):
        assert client.post(self.URL, json={}).status_code == 422

    def test_invalid_db_type_422(self, client):
        r = client.post(self.URL, json={
            "host": "localhost", "port": 3306,
            "username": "root", "password": "p",
            "database": "db", "database_type": "oracle",
        })
        assert r.status_code == 422

    def test_invalid_port_422(self, client):
        r = client.post(self.URL, json={
            "host": "localhost", "port": 99999,
            "username": "root", "password": "p",
            "database": "db", "database_type": "mysql",
        })
        assert r.status_code == 422

    def test_unreachable_host_400(self, client):
        r = client.post(self.URL, json={
            "host": "no.such.host.invalid", "port": 3306,
            "username": "root", "password": "p",
            "database": "db", "database_type": "mysql",
        })
        assert r.status_code == 400
        assert r.json()["success"] is False


# ── Query routes ──────────────────────────────────────────────────────────────
class TestQueryExecute:
    URL = "/api/v1/query/execute"

    def test_missing_body_422(self, client):
        assert client.post(self.URL, json={}).status_code == 422

    def test_empty_sql_422(self, client):
        r = client.post(self.URL, json={
            "sql_query": "", "host": "h", "port": 3306,
            "username": "u", "password": "p",
            "database": "db", "database_type": "mysql",
        })
        assert r.status_code == 422

    def test_row_limit_too_large_422(self, client):
        r = client.post(self.URL, json={
            "sql_query": "SELECT 1", "row_limit": 9999999,
            "host": "h", "port": 3306, "username": "u",
            "password": "p", "database": "db", "database_type": "mysql",
        })
        assert r.status_code == 422


# ── Export routes ─────────────────────────────────────────────────────────────
class TestExport:
    def test_csv_empty_400(self, client):
        r = client.post("/api/v1/export/csv", json={
            "columns": ["id"], "rows": [], "filename": "f"
        })
        assert r.status_code == 400

    def test_csv_with_data_200(self, client):
        r = client.post("/api/v1/export/csv", json={
            "columns": ["id", "name"],
            "rows": [{"id": 1, "name": "Alice"}],
            "filename": "out",
        })
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]

    def test_excel_with_data_200(self, client):
        r = client.post("/api/v1/export/excel", json={
            "columns": ["id", "name"],
            "rows": [{"id": 1, "name": "Bob"}],
            "filename": "out",
        })
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers["content-type"]

    def test_excel_empty_400(self, client):
        r = client.post("/api/v1/export/excel", json={
            "columns": ["id"], "rows": [], "filename": "empty"
        })
        assert r.status_code == 400


# ── History routes ────────────────────────────────────────────────────────────
class TestHistory:
    def test_list_200(self, client):
        r = client.get("/api/v1/history")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_get_nonexistent_404(self, client):
        assert client.get("/api/v1/history/99999").status_code == 404

    def test_delete_nonexistent_404(self, client):
        assert client.delete("/api/v1/history/99999").status_code == 404

    def test_pagination(self, client):
        r = client.get("/api/v1/history?page=1&page_size=5")
        assert r.status_code == 200
        b = r.json()
        assert b["page"] == 1 and b["page_size"] == 5

    def test_invalid_page_422(self, client):
        assert client.get("/api/v1/history?page=0").status_code == 422


# ── Database Upload routes ───────────────────────────────────────────────────
class TestDatabaseUpload:
    URL = "/api/v1/database/upload"

    def test_upload_multiple_csv_files(self, client):
        files = [
            ("files", ("t1.csv", b"id,name\n1,Alice\n2,Bob")),
            ("files", ("t2.csv", b"id,val\n1,10.5\n2,20.0"))
        ]
        r = client.post(self.URL, files=files)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "t1 & t2" in data["data"]["database"]
        assert "unified_" in data["data"]["file_path"]
        assert data["data"]["file_path"].endswith(".db")

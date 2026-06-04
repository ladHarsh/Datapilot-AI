"""
tests/test_database.py
───────────────────────
Unit tests for database-layer components:
  • SQL validation (security gate)
  • Schema loader (against in-memory SQLite)
  • Query executor (against in-memory SQLite)
  • Connection manager caching

Run with:
    cd backend
    pytest app/tests/test_database.py -v
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.core.exceptions import InvalidSQLException, SchemaLoadError
from app.db.connectors.connection_manager import ConnectionManager
from app.db.schema_loader import format_schema_for_ai, load_schema
from app.services.database.query_executor import (
    _inject_limit,
    execute_query,
    validate_sql,
)


# ══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def sqlite_engine():
    """In-memory SQLite engine pre-seeded with sample data."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE customers (
                id   INTEGER PRIMARY KEY,
                name TEXT    NOT NULL,
                age  INTEGER
            )
        """))
        conn.execute(text("""
            CREATE TABLE orders (
                id          INTEGER PRIMARY KEY,
                customer_id INTEGER,
                total       REAL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
        """))
        conn.execute(text("INSERT INTO customers VALUES (1,'Alice',30),(2,'Bob',25)"))
        conn.execute(text("INSERT INTO orders VALUES (1,1,99.9),(2,2,49.5)"))
        conn.commit()
    yield engine
    engine.dispose()


# ══════════════════════════════════════════════════════════════════════════════
#  SQL Validation Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateSQL:
    """Security gate: only SELECT is allowed."""

    def test_valid_select_passes(self):
        validate_sql("SELECT id, name FROM customers")

    def test_select_with_where_passes(self):
        validate_sql("SELECT * FROM orders WHERE total > 50 LIMIT 10")

    def test_empty_string_raises(self):
        with pytest.raises(InvalidSQLException, match="empty"):
            validate_sql("")

    def test_whitespace_only_raises(self):
        with pytest.raises(InvalidSQLException, match="empty"):
            validate_sql("   ")

    def test_drop_table_raises(self):
        with pytest.raises(InvalidSQLException):
            validate_sql("DROP TABLE customers")

    def test_delete_raises(self):
        with pytest.raises(InvalidSQLException):
            validate_sql("DELETE FROM customers WHERE id=1")

    def test_insert_raises(self):
        with pytest.raises(InvalidSQLException):
            validate_sql("INSERT INTO customers VALUES (3,'Eve',22)")

    def test_update_raises(self):
        with pytest.raises(InvalidSQLException):
            validate_sql("UPDATE customers SET age=31 WHERE id=1")

    def test_truncate_raises(self):
        with pytest.raises(InvalidSQLException):
            validate_sql("TRUNCATE TABLE customers")

    def test_alter_raises(self):
        with pytest.raises(InvalidSQLException):
            validate_sql("ALTER TABLE customers ADD COLUMN email TEXT")

    def test_create_raises(self):
        with pytest.raises(InvalidSQLException):
            validate_sql("CREATE TABLE foo (id INT)")

    def test_select_with_blocked_keyword_in_subquery_raises(self):
        with pytest.raises(InvalidSQLException):
            validate_sql("SELECT * FROM (DELETE FROM customers) AS t")

    def test_line_comment_stripping_passes(self):
        validate_sql("-- fetch all customers\nSELECT * FROM customers")

    def test_block_comment_stripping_passes(self):
        validate_sql("/* get data */ SELECT id FROM customers")


# ══════════════════════════════════════════════════════════════════════════════
#  Limit Injection Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestInjectLimit:
    def test_adds_limit_when_absent(self):
        sql = _inject_limit("SELECT * FROM customers", 100)
        assert "LIMIT 100" in sql

    def test_does_not_double_limit(self):
        sql = _inject_limit("SELECT * FROM customers LIMIT 50", 100)
        assert sql.count("LIMIT") == 1

    def test_strips_trailing_semicolon(self):
        sql = _inject_limit("SELECT * FROM customers;", 10)
        assert sql.endswith("LIMIT 10")

    def test_case_insensitive_limit_detection(self):
        sql = _inject_limit("SELECT * FROM t limit 5", 100)
        assert sql.count("imit") == 1   # only one LIMIT clause


# ══════════════════════════════════════════════════════════════════════════════
#  Schema Loader Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaLoader:
    def test_returns_expected_tables(self, sqlite_engine):
        schema = load_schema(sqlite_engine, force_refresh=True)
        table_names = [t["name"] for t in schema["tables"]]
        assert "customers" in table_names
        assert "orders" in table_names

    def test_table_count_correct(self, sqlite_engine):
        schema = load_schema(sqlite_engine, force_refresh=True)
        assert schema["table_count"] == 2

    def test_customers_columns(self, sqlite_engine):
        schema = load_schema(sqlite_engine, force_refresh=True)
        customers = next(t for t in schema["tables"] if t["name"] == "customers")
        col_names = [c["name"] for c in customers["columns"]]
        assert "id" in col_names
        assert "name" in col_names
        assert "age" in col_names

    def test_primary_key_detected(self, sqlite_engine):
        schema = load_schema(sqlite_engine, force_refresh=True)
        customers = next(t for t in schema["tables"] if t["name"] == "customers")
        assert "id" in customers["primary_keys"]

    def test_schema_has_dialect(self, sqlite_engine):
        schema = load_schema(sqlite_engine, force_refresh=True)
        assert schema["dialect"] == "sqlite"

    def test_cache_returns_same_object(self, sqlite_engine):
        s1 = load_schema(sqlite_engine)
        s2 = load_schema(sqlite_engine)
        assert s1 is s2   # same cached dict

    def test_force_refresh_bypasses_cache(self, sqlite_engine):
        s1 = load_schema(sqlite_engine)
        s2 = load_schema(sqlite_engine, force_refresh=True)
        assert s1["table_count"] == s2["table_count"]

    def test_ai_prompt_format_contains_table_names(self, sqlite_engine):
        schema = load_schema(sqlite_engine, force_refresh=True)
        prompt = format_schema_for_ai(schema)
        assert "customers" in prompt
        assert "orders" in prompt

    def test_ai_prompt_format_contains_pk_annotation(self, sqlite_engine):
        schema = load_schema(sqlite_engine, force_refresh=True)
        prompt = format_schema_for_ai(schema)
        assert "PK" in prompt


# ══════════════════════════════════════════════════════════════════════════════
#  Query Executor Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestQueryExecutor:
    def test_simple_select_returns_rows(self, sqlite_engine):
        result = execute_query(sqlite_engine, "SELECT * FROM customers")
        assert result["row_count"] == 2
        assert "id" in result["columns"]

    def test_columns_match_schema(self, sqlite_engine):
        result = execute_query(sqlite_engine, "SELECT name, age FROM customers")
        assert result["columns"] == ["name", "age"]

    def test_row_limit_applied(self, sqlite_engine):
        result = execute_query(sqlite_engine, "SELECT * FROM customers", row_limit=1)
        assert result["row_count"] == 1
        assert result["truncated"] is True

    def test_execution_duration_positive(self, sqlite_engine):
        result = execute_query(sqlite_engine, "SELECT * FROM customers")
        assert result["execution_duration"] > 0

    def test_user_query_echoed(self, sqlite_engine):
        result = execute_query(
            sqlite_engine,
            "SELECT * FROM customers",
            user_query="show all customers",
        )
        assert result["user_query"] == "show all customers"

    def test_dml_insert_and_delete_are_blocked(self, sqlite_engine):
        # Verify INSERT is blocked
        with pytest.raises(InvalidSQLException, match="Security Warning"):
            execute_query(sqlite_engine, "INSERT INTO customers VALUES (99,'Z',20)")
        
        # Verify DELETE is blocked
        with pytest.raises(InvalidSQLException, match="Security Warning"):
            execute_query(sqlite_engine, "DELETE FROM customers WHERE id=1")

    def test_join_query_works(self, sqlite_engine):
        sql = (
            "SELECT c.name, o.total "
            "FROM customers c JOIN orders o ON c.id = o.customer_id"
        )
        result = execute_query(sqlite_engine, sql)
        assert result["row_count"] == 2
        assert "name" in result["columns"]
        assert "total" in result["columns"]

    def test_aggregate_query_works(self, sqlite_engine):
        result = execute_query(
            sqlite_engine, "SELECT COUNT(*) AS cnt FROM customers"
        )
        assert result["row_count"] == 1
        assert result["rows"][0]["cnt"] == 2

    def test_empty_result_returns_zero_rows(self, sqlite_engine):
        result = execute_query(
            sqlite_engine,
            "SELECT * FROM customers WHERE id = 9999",
        )
        assert result["row_count"] == 0
        assert result["rows"] == []


# ══════════════════════════════════════════════════════════════════════════════
#  Connection Manager Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestConnectionManager:
    def test_singleton_returns_same_instance(self):
        a = ConnectionManager.instance()
        b = ConnectionManager.instance()
        assert a is b

    def test_get_or_create_caches_engine(self):
        mgr = ConnectionManager()

        call_count = {"n": 0}

        def fake_factory(**kwargs):
            call_count["n"] += 1
            return create_engine("sqlite:///:memory:")

        mgr.get_or_create("sqlite", "h", 1, "u", "p", "db", fake_factory)
        mgr.get_or_create("sqlite", "h", 1, "u", "p", "db", fake_factory)

        assert call_count["n"] == 1   # factory called only once

    def test_remove_disposes_engine(self):
        mgr = ConnectionManager()

        def fake_factory(**kwargs):
            return create_engine("sqlite:///:memory:")

        mgr.get_or_create("sqlite", "localhost", 1234, "user", "pass", "mydb", fake_factory)
        before = mgr.active_count
        mgr.remove("sqlite", "localhost", 1234, "user", "mydb")
        assert mgr.active_count == before - 1

    def test_dispose_all_clears_engines(self):
        mgr = ConnectionManager()

        def ff(**kwargs):
            return create_engine("sqlite:///:memory:")

        mgr.get_or_create("sqlite", "a", 1, "u", "p", "d1", ff)
        mgr.get_or_create("sqlite", "b", 2, "u", "p", "d2", ff)
        mgr.dispose_all()
        assert mgr.active_count == 0


# ══════════════════════════════════════════════════════════════════════════════
#  Upload Service Merging Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestUploadService:
    def test_process_upload_multiple_files(self, tmp_path, monkeypatch):
        # Set settings.UPLOAD_FOLDER to a temp directory
        monkeypatch.setattr("app.core.config.settings.UPLOAD_FOLDER", str(tmp_path))

        # 1. Create a SQLite DB as bytes
        import sqlite3
        db1_path = tmp_path / "test1.db"
        conn = sqlite3.connect(db1_path)
        conn.execute("CREATE TABLE t1 (id INT, val TEXT);")
        conn.execute("INSERT INTO t1 VALUES (1, 'apple'), (2, 'banana');")
        conn.commit()
        conn.close()
        db1_bytes = db1_path.read_bytes()

        # 2. Create a CSV as bytes
        csv_bytes = b"id,val\n3,cherry\n4,date\n"

        # 3. Call process_upload with both
        from app.services.database.upload_service import process_upload
        config = process_upload(
            files=[(db1_bytes, "test1.db"), (csv_bytes, "test2.csv")],
            user_id=123
        )

        # 4. Verify config return
        assert config["database_type"] == "sqlite"
        assert "unified_" in config["file_path"]
        assert "test1 & test2" in config["database"]

        # 5. Connect and verify tables inside unified DB
        unified_conn = sqlite3.connect(config["file_path"])
        cursor = unified_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        assert "t1" in tables
        assert "test2" in tables

        # Verify data inside t1
        cursor.execute("SELECT * FROM t1;")
        t1_rows = cursor.fetchall()
        assert len(t1_rows) == 2
        assert t1_rows[0] == (1, 'apple')

        # Verify data inside test2 (CSV table)
        cursor.execute("SELECT * FROM test2;")
        test2_rows = cursor.fetchall()
        assert len(test2_rows) == 2
        assert test2_rows[0] == (3, 'cherry')

        unified_conn.close()

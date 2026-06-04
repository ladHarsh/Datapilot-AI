"""
services/database/upload_service.py
────────────────────────────────────
Save uploaded SQLite/CSV files and produce connection configuration.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from app.core.config import settings
from app.core.exceptions import DatabaseConnectionError

_TABLE_NAME_RE = re.compile(r"[^a-zA-Z0-9_]")


def _sanitize_table_name(name: str) -> str:
    cleaned = _TABLE_NAME_RE.sub("_", name.strip()) or "data"
    if cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned[:64]


def _user_upload_dir(user_id: int) -> Path:
    base = Path(settings.UPLOAD_FOLDER)
    path = base / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def csv_to_sqlite(csv_bytes: bytes, dest_db: Path, table_name: str) -> None:
    """Import CSV rows into a new SQLite database file."""
    df = pd.read_csv(io.BytesIO(csv_bytes))
    if df.empty:
        raise DatabaseConnectionError(
            "CSV file is empty.",
            detail={"table": table_name},
        )
    engine = create_engine(f"sqlite:///{dest_db.resolve().as_posix()}")
    try:
        df.to_sql(table_name, engine, index=False, if_exists="replace")
    finally:
        engine.dispose()


def process_upload(
    files: list[tuple[bytes, str]],
    user_id: int,
) -> dict:
    """
    Persist uploaded SQLite/CSV files and merge them into a single SQLite database.
    Returns a connection configuration for the merged database.
    """
    if not files:
        raise DatabaseConnectionError("No files provided.")

    import time
    upload_dir = _user_upload_dir(user_id)
    db_path = upload_dir / f"unified_{int(time.time() * 1000)}.db"

    display_names = []
    import sqlite3

    for file_bytes, filename in files:
        if not file_bytes:
            continue
        safe_name = Path(filename).name.replace("..", "_").replace("/", "_").replace("\\", "_")
        ext = Path(safe_name).suffix.lower()
        stem = Path(safe_name).stem

        display_names.append(stem)

        if ext == ".csv":
            table_name = _sanitize_table_name(stem)
            try:
                # Read CSV
                df = pd.read_csv(io.BytesIO(file_bytes))
                if df.empty:
                    raise DatabaseConnectionError(f"CSV file '{filename}' is empty.")
                
                # Write CSV to SQLite unified database
                engine = create_engine(f"sqlite:///{db_path.resolve().as_posix()}")
                try:
                    df.to_sql(table_name, engine, index=False, if_exists="replace")
                finally:
                    engine.dispose()
            except Exception as e:
                raise DatabaseConnectionError(f"Failed to process CSV file '{filename}': {str(e)}")

        elif ext in (".sqlite", ".db", ".sqlite3"):
            # Write SQLite to temp file, then merge tables
            temp_db_path = upload_dir / f"temp_{safe_name}"
            temp_db_path.write_bytes(file_bytes)

            try:
                # Retrieve all tables
                src_conn = sqlite3.connect(temp_db_path)
                cursor = src_conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                src_conn.close()

                # Read each table via pandas and write to the unified SQLite DB
                src_engine = create_engine(f"sqlite:///{temp_db_path.resolve().as_posix()}")
                dest_engine = create_engine(f"sqlite:///{db_path.resolve().as_posix()}")
                try:
                    for table in tables:
                        # Preserve original table names from SQLite files.
                        # Only apply sanitization for CSV files where the table
                        # name comes from the filename and may contain invalid chars.
                        df = pd.read_sql_query(f'SELECT * FROM "{table}"', src_engine)
                        df.to_sql(table, dest_engine, index=False, if_exists="replace")
                finally:
                    src_engine.dispose()
                    dest_engine.dispose()
            except Exception as e:
                raise DatabaseConnectionError(
                    f"Failed to process SQLite database '{filename}': {str(e)}"
                )
            finally:
                if temp_db_path.exists():
                    try:
                        temp_db_path.unlink()
                    except Exception:
                        pass
        elif ext == ".sql":
            try:
                sql_content = file_bytes.decode("utf-8", errors="ignore")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.executescript(sql_content)
                conn.commit()
                conn.close()
            except Exception as e:
                raise DatabaseConnectionError(
                    f"Failed to process SQL script '{filename}': {str(e)}"
                )
        else:
            raise DatabaseConnectionError(
                f"Unsupported file type '{ext}' for file '{filename}'. Use .sqlite, .db, .csv, or .sql."
            )

    resolved = db_path.resolve()
    if not resolved.is_file():
        raise DatabaseConnectionError("Failed to create unified database.")

    if len(display_names) > 2:
        db_display_name = ", ".join(display_names[:2]) + f" & {len(display_names) - 2} more"
    elif len(display_names) == 2:
        db_display_name = " & ".join(display_names)
    elif len(display_names) == 1:
        db_display_name = display_names[0]
    else:
        db_display_name = "Merged Dataset"

    return {
        "database_type": "sqlite",
        "file_path": str(resolved),
        "database": db_display_name,
        "host": "local",
        "port": 0,
        "username": "sqlite",
        "password": "",
        "source_filename": ", ".join(display_names),
    }

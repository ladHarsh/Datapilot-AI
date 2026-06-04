"""
Connection Manager — DataPilot AI
Utility for persistent storage and management of database connection metadata
without saving sensitive passwords.
"""
import os
import json
import hashlib
from datetime import datetime
import streamlit as st

FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONNECTIONS_FILE = os.path.join(FRONTEND_DIR, ".connections.json")

def get_saved_connections(username: str | None = None) -> list:
    """Read saved database connection details from .connections.json for a specific user."""
    if not username:
        username = st.session_state.get("user_profile", {}).get("username", "default")

    if not os.path.exists(CONNECTIONS_FILE):
        return []
    try:
        with open(CONNECTIONS_FILE, "r") as f:
            raw_data = json.load(f)
            
            if isinstance(raw_data, list):
                # Legacy format: migrate legacy list to "default" key
                user_connections = raw_data
            elif isinstance(raw_data, dict):
                user_connections = raw_data.get(username, [])
            else:
                return []

            # ── Deduplicate SQLite entries by source_filename (keep most recent) ──
            seen_filenames: dict = {}
            deduped: list = []
            for conn in user_connections:
                sf = conn.get("source_filename")
                db_type = conn.get("database_type", "").lower()
                if db_type == "sqlite" and sf:
                    if sf not in seen_filenames:
                        seen_filenames[sf] = len(deduped)
                        deduped.append(conn)
                    else:
                        # Keep whichever was last connected
                        existing = deduped[seen_filenames[sf]]
                        if conn.get("last_connected", "") > existing.get("last_connected", ""):
                            conn["usage_count"] = existing.get("usage_count", 1) + conn.get("usage_count", 1)
                            deduped[seen_filenames[sf]] = conn
                        else:
                            deduped[seen_filenames[sf]]["usage_count"] = (
                                existing.get("usage_count", 1) + conn.get("usage_count", 1)
                            )
                else:
                    deduped.append(conn)
            user_connections = deduped

            # Sort: Favorites first, then recency (newest last_connected first)
            def sort_key(item):
                fav = item.get("is_favorite", False)
                last_conn = item.get("last_connected", "")
                return (fav, last_conn)

            user_connections.sort(key=sort_key, reverse=True)
            return user_connections
    except Exception as e:
        # Fallback to session state if JSON load fails for any reason
        return st.session_state.get(f"fallback_connections_{username}", [])

def _save_to_json(connections: list, username: str | None = None) -> bool:
    """Write connection metadata list back to .connections.json under the user's key."""
    if not username:
        username = st.session_state.get("user_profile", {}).get("username", "default")
    try:
        raw_data = {}
        if os.path.exists(CONNECTIONS_FILE):
            try:
                with open(CONNECTIONS_FILE, "r") as f:
                    raw_data = json.load(f)
                    if isinstance(raw_data, list):
                        raw_data = {"default": raw_data}
                    elif not isinstance(raw_data, dict):
                        raw_data = {}
            except Exception:
                raw_data = {}
        
        # Update this user's entry
        raw_data[username] = connections
        
        with open(CONNECTIONS_FILE, "w") as f:
            json.dump(raw_data, f, indent=4)
        return True
    except Exception as e:
        st.session_state[f"fallback_connections_{username}"] = connections
        return False

def save_connection(host: str, port: int, username: str, database: str, database_type: str, file_path: str | None = None, source_filename: str | None = None) -> None:
    """Save or update successful database connection details without the password."""
    if not host or not username or not database or not database_type:
        return

    # Normalize fields
    db_type = database_type.lower()
    
    # Calculate a unique ID based on credentials/file_path to avoid duplicates
    if db_type == "sqlite" and file_path:
        unique_str = f"sqlite://{file_path}"
    else:
        unique_str = f"{db_type}://{username}@{host}:{port}/{database}"
    conn_id = hashlib.md5(unique_str.encode()).hexdigest()

    current_user = st.session_state.get("user_profile", {}).get("username", "default")
    connections = get_saved_connections(current_user)

    # Primary lookup: exact conn_id match
    existing_index = -1
    for idx, conn in enumerate(connections):
        if conn.get("id") == conn_id:
            existing_index = idx
            break

    # Secondary lookup for SQLite uploads: same source_filename
    # (each upload produces a new file_path so conn_id differs, but the file is the same)
    if existing_index == -1 and db_type == "sqlite" and source_filename:
        for idx, conn in enumerate(connections):
            if (
                conn.get("database_type", "").lower() == "sqlite"
                and conn.get("source_filename") == source_filename
            ):
                existing_index = idx
                # Update the stored conn_id to the new hash (new file_path)
                connections[existing_index]["id"] = conn_id
                break

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if existing_index != -1:
        # Update existing record
        connections[existing_index]["last_connected"] = now_str
        connections[existing_index]["usage_count"] = connections[existing_index].get("usage_count", 0) + 1
        if file_path:
            connections[existing_index]["file_path"] = file_path
        if source_filename:
            connections[existing_index]["source_filename"] = source_filename
    else:
        # Create a new connection record
        new_conn = {
            "id": conn_id,
            "database": database,
            "host": host,
            "port": int(port),
            "username": username,
            "database_type": db_type,
            "last_connected": now_str,
            "is_favorite": False,
            "usage_count": 1
        }
        if file_path:
            new_conn["file_path"] = file_path
        if source_filename:
            new_conn["source_filename"] = source_filename

        connections.append(new_conn)

    _save_to_json(connections, current_user)

def delete_saved_connection(conn_id: str) -> None:
    """Remove a saved connection from list."""
    current_user = st.session_state.get("user_profile", {}).get("username", "default")
    connections = get_saved_connections(current_user)
    connections = [c for c in connections if c.get("id") != conn_id]
    _save_to_json(connections, current_user)

def toggle_favorite(conn_id: str) -> None:
    """Pin/Unpin a connection as a favorite."""
    current_user = st.session_state.get("user_profile", {}).get("username", "default")
    connections = get_saved_connections(current_user)
    for conn in connections:
        if conn.get("id") == conn_id:
            conn["is_favorite"] = not conn.get("is_favorite", False)
            break
    _save_to_json(connections, current_user)

def reconnect_database(conn: dict, password: str) -> tuple[bool, str]:
    """Execute a full reconnection sequence with provided password."""
    from services.api_client import connect_db
    from utils.db_context import load_database_context
    
    host = conn.get("host")
    port = str(conn.get("port"))
    username = conn.get("username")
    database = conn.get("database")
    db_type = conn.get("database_type")
    file_path = conn.get("file_path")
    source_filename = conn.get("source_filename")

    # 1. Trigger API connect request
    result = connect_db(host, port, username, password, database, db_type, file_path=file_path)
    
    if result.get("success") or result.get("status") == "ok":
        # Save session parameters in st.session_state
        st.session_state["connected"] = True
        db_info = {
            "host": host,
            "port": int(port),
            "username": username,
            "password": password,
            "database": database,
            "database_type": db_type.lower(),
        }
        if file_path:
            db_info["file_path"] = file_path
        if source_filename:
            db_info["source_filename"] = source_filename
            
        st.session_state["db_info"] = db_info

        # 2. Extract database schema/metrics
        ok, msg = load_database_context(db_info)
        if ok:
            # 3. Update connection history details (timestamp & counter)
            save_connection(host, int(port), username, database, db_type, file_path=file_path, source_filename=source_filename)
            # 4. Persist full db_info for refresh restore
            _uname = st.session_state.get("user_profile", {}).get("username", "default")
            save_active_session(_uname, db_info)
            try:
                from utils.settings_manager import log_activity
                log_activity(f"Reconnected to database: '{database}' ({db_type.upper()})")
            except Exception:
                pass
            return True, "Reconnected successfully!"
        else:
            st.session_state["connected"] = False
            return False, f"Credentials accepted but schema load failed: {msg}"
    else:
        error_msg = result.get("message", "Incorrect password or network unreachable.")
        return False, error_msg

def get_relative_time(timestamp_str: str) -> str:
    """Return a relative, user-friendly description of time elapsed since connection."""
    if not timestamp_str:
        return "Never"
    try:
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        diff = datetime.now() - dt
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "Just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{int(minutes)}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{int(hours)}h ago"
        days = hours // 24
        if days < 30:
            return f"{int(days)}d ago"
        return dt.strftime("%b %d, %Y")
    except Exception:
        return "Unknown"


# ── Active session persistence (survives page refresh) ────────────────────── #

_SESSION_FILE = os.path.join(FRONTEND_DIR, ".active_session.json")


def _read_session_file() -> dict:
    """Read the full session JSON (returns {} on any error)."""
    try:
        if os.path.exists(_SESSION_FILE):
            with open(_SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _write_session_file(data: dict) -> None:
    try:
        with open(_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def save_active_session(username: str, db_info: dict) -> None:
    """Persist the active db_info (including password) keyed by username."""
    data = _read_session_file()
    entry = data.get(username, {})
    entry["db_info"] = db_info
    data[username] = entry
    _write_session_file(data)


def load_active_session(username: str) -> dict | None:
    """Return the persisted db_info for *username*, or None if not found."""
    data = _read_session_file()
    entry = data.get(username)
    if entry and isinstance(entry, dict):
        # Support both old format (flat db_info) and new format ({db_info: {...}})
        return entry.get("db_info") if "db_info" in entry else entry
    return None


def save_auth_credentials(username: str, password: str) -> None:
    """Persist login credentials so we can silently re-login on refresh.
    This file is local-only and MUST NOT be committed to version control.
    """
    data = _read_session_file()
    entry = data.get(username, {})
    entry["auth"] = {"username": username, "password": password}
    data[username] = entry
    _write_session_file(data)


def load_auth_credentials(username: str) -> dict | None:
    """Return saved auth credentials for *username*, or None."""
    data = _read_session_file()
    entry = data.get(username, {})
    return entry.get("auth")


def load_any_auth_credentials() -> dict | None:
    """Return the first saved auth credentials found (used when username is unknown)."""
    data = _read_session_file()
    for entry in data.values():
        if isinstance(entry, dict) and "auth" in entry:
            return entry["auth"]
    return None


def clear_active_session(username: str) -> None:
    """Remove the persisted session for *username* (called on explicit disconnect)."""
    data = _read_session_file()
    data.pop(username, None)
    _write_session_file(data)

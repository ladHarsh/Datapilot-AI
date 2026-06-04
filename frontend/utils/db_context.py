"""Load schema, stats, and suggestions after a database connection."""

import streamlit as st

from services.api_client import get_database_stats, get_schema
from utils.db_helpers import is_valid_db_info, normalize_db_info
from utils.schema_helpers import build_query_suggestions, schema_for_viewer


def load_database_context(db_info: dict, force_refresh: bool = False) -> tuple[bool, str]:
    """
    Fetch schema + stats from backend and store in session state.

    Parameters
    ----------
    db_info       : Active connection parameters.
    force_refresh : Bypass the backend schema TTL cache. Set True after any
                    file upload (CSV / SQLite) because the unified_database.db
                    file is recreated and the cached schema is stale.

    Returns (success, message).
    """
    normalized = normalize_db_info(db_info)
    if not normalized:
        st.session_state["schema_loaded"] = False
        return False, "Incomplete connection details. Please reconnect using Connect Database."

    schema_resp = get_schema(normalized, force_refresh=force_refresh)
    if not schema_resp.get("success"):
        st.session_state["schema_loaded"] = False
        msg = schema_resp.get("message", "Failed to load schema.")
        st.session_state["schema_load_error"] = msg
        return False, msg

    schema_data = schema_resp.get("data") or {}
    st.session_state["schema_raw"] = schema_data
    st.session_state["schema_data"] = schema_for_viewer(schema_data)
    st.session_state["query_suggestions"] = build_query_suggestions(schema_data)
    st.session_state["schema_loaded"] = True
    st.session_state["schema_load_error"] = None

    stats_resp = get_database_stats(normalized)
    if stats_resp.get("success"):
        st.session_state["db_stats"] = stats_resp.get("data") or {}
    else:
        st.session_state["db_stats"] = {
            "total_rows": 0,
            "active_users": 0,
            "table_count": schema_data.get("table_count", 0),
        }

    # Keep normalized credentials for API calls
    st.session_state["db_info"] = normalized

    # Load query history specifically for this database
    try:
        from services.api_client import fetch_query_history
        loaded = fetch_query_history(limit=30, database_name=normalized.get("database"))
        st.session_state["query_history"] = loaded
    except Exception:
        pass

    return True, schema_resp.get("message", "Database context loaded.")

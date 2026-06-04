import json
import requests
import streamlit as st

from utils.db_helpers import first_table_name, normalize_db_info

# Backend API endpoint (with version prefix)
BASE_URL = "http://127.0.0.1:8000/api/v1"


def get_headers():
    headers = {"Content-Type": "application/json"}
    if st.session_state.get("access_token"):
        headers["Authorization"] = f"Bearer {st.session_state['access_token']}"
    return headers


def _parse_response(response):
    """Normalize FastAPI SuccessResponse or error payloads."""
    try:
        body = response.json()
    except Exception:
        return {"success": False, "message": response.text or f"HTTP {response.status_code}"}

    if response.status_code == 401:
        detail = body.get("detail", "Unauthorized. Please log in again.")
        return {"success": False, "message": detail}

    if response.status_code >= 400:
        if isinstance(body, dict) and isinstance(body.get("message"), str) and body.get("message").strip():
            error_msg = body["message"]
        else:
            detail = body.get("detail", f"HTTP {response.status_code}")
            if isinstance(detail, dict):
                error_msg = detail.get("message", str(detail))
            elif isinstance(detail, list):
                try:
                    error_msg = "; ".join([f"{err.get('loc', [])}: {err.get('msg', '')}" for err in detail])
                except Exception:
                    error_msg = str(detail)
            else:
                error_msg = str(detail)
        return {"success": False, "message": error_msg, "error": error_msg}

    # SuccessResponse wrapper
    if isinstance(body, dict) and "data" in body and "success" in body:
        return body

    # Direct models (e.g. QueryResponse)
    if isinstance(body, dict) and body.get("success") is not False:
        body.setdefault("success", True)
        return body

    return body


def upload_database(files_input, filename: str | None = None):
    """
    Upload multiple or single SQLite/CSV files and connect.
    Supports:
      - Old signature: upload_database(file_bytes: bytes, filename: str)
      - New signature: upload_database(files: list[UploadedFile] | UploadedFile)
    """
    try:
        headers = {}
        if st.session_state.get("access_token"):
            headers["Authorization"] = f"Bearer {st.session_state['access_token']}"

        files_list = []
        if filename is not None and isinstance(files_input, bytes):
            # Old signature usage
            files_list.append((filename, files_input))
        elif isinstance(files_input, list):
            # List of UploadedFiles or (filename, bytes) tuples
            for f in files_input:
                if isinstance(f, tuple):
                    files_list.append(f)
                else:
                    files_list.append((f.name, f.getvalue()))
        else:
            # Single UploadedFile
            files_list.append((files_input.name, files_input.getvalue()))

        # Build multipart payload for requests
        # FastAPI multiple files expects list of ('files', (name, content)) tuples
        files_payload = [("files", (name, content)) for name, content in files_list]

        response = requests.post(
            f"{BASE_URL}/database/upload",
            files=files_payload,
            headers=headers,
            timeout=180,
        )
        return _parse_response(response)
    except Exception as e:
        return {"success": False, "message": f"Upload failed: {str(e)}"}


def fetch_query_history(limit: int = 30, database_name: str | None = None) -> list:
    """Fetch the user's recent query history from the backend database.
    Returns a list of history dicts suitable for session_state["query_history"].
    """
    try:
        params = {"page": 1, "page_size": limit}
        if database_name:
            params["database_name"] = database_name
        response = requests.get(
            f"{BASE_URL}/history",
            params=params,
            headers=get_headers(),
            timeout=15,
        )
        if response.status_code != 200:
            return []
        body = response.json()
        items = body.get("items", [])
        result = []
        for item in items:
            user_query = item.get("user_query", "")
            generated_sql = item.get("generated_sql", "")
            if not user_query and not generated_sql:
                continue
            from components.sidebar import _smart_title
            title = item.get("query_title") or _smart_title(user_query or generated_sql)
            result.append({
                "query":              user_query,
                "sql":                generated_sql,
                "title":              title,
                "timestamp":          item.get("created_at", ""),
                "result":             None,  # Full result not stored in DB — will re-run on click
                "database_name":      item.get("database_name"),
                "execution_duration": item.get("execution_duration", 0.0),
            })
        return result
    except Exception:
        return []


def connect_db(host, port, username, password, database, database_type, file_path: str | None = None):
    """Call backend to validate and establish a database connection."""
    normalized = normalize_db_info({
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "database": database,
        "database_type": database_type,
        "file_path": file_path,
    })
    if not normalized:
        return {"success": False, "message": "Please fill in all connection fields."}

    try:
        response = requests.post(
            f"{BASE_URL}/database/connect",
            json=normalized,
            headers=get_headers(),
            timeout=45,
        )
        return _parse_response(response)
    except Exception as e:
        return {"success": False, "message": f"Connection failed: {str(e)}"}


def get_database_stats(db_info):
    """Fetch row counts and table statistics for the connected database."""
    normalized = normalize_db_info(db_info)
    if not normalized:
        return {"success": False, "message": "Missing connection details."}

    try:
        response = requests.post(
            f"{BASE_URL}/database/stats",
            json=normalized,
            headers=get_headers(),
            timeout=30,
        )
        return _parse_response(response)
    except Exception as e:
        return {"success": False, "message": f"Stats fetch failed: {str(e)}"}


def get_schema(db_info, force_refresh: bool = False):
    """Fetch the database schema from the backend.

    Parameters
    ----------
    db_info       : Connection details dict.
    force_refresh : When True, bypasses the backend 5-minute TTL cache.
                    Always set True after a file upload so stale cached
                    schema from the previous unified_database.db is discarded.
    """
    normalized = normalize_db_info(db_info)
    if not normalized:
        return {"success": False, "message": "Missing connection details."}

    try:
        response = requests.post(
            f"{BASE_URL}/database/schema",
            json=normalized,
            params={"force_refresh": "true"} if force_refresh else {},
            headers=get_headers(),
            timeout=60,
        )
        return _parse_response(response)
    except Exception as e:
        return {"success": False, "message": f"Schema fetch failed: {str(e)}"}


def _default_sql(db_info: dict) -> str:
    """Build a safe starter SELECT using a real table name."""
    table = first_table_name(st.session_state.get("schema_data"))
    if not table:
        return "SELECT 1 AS connected"
    db_type = db_info.get("database_type", "mysql")
    if db_type == "sqlite":
        return f'SELECT * FROM "{table}" LIMIT 10'
    if db_type == "postgresql":
        return f'SELECT * FROM "{table}" LIMIT 10'
    return f"SELECT * FROM `{table}` LIMIT 10"


def _build_fast_analyze_payload(query: str, db_info: dict) -> dict:
    """Build the shared request payload for fast-analyze and stream-analyze."""
    from utils.settings_manager import get_setting
    normalized = normalize_db_info(db_info) or {}
    raw_exp = get_setting("explanation_mode")
    explanation_mode = "Detailed" if "Detailed" in raw_exp else ("Brief" if "Short" in raw_exp else "None")
    limit_mode = get_setting("row_limit_mode")
    row_limit = get_setting("row_limit") if limit_mode == "Limited" else 500
    return {
        "user_query":       query,
        "ai_model":         get_setting("ai_model"),
        "explanation_mode": explanation_mode,
        "auto_insights":    bool(get_setting("auto_insights")),
        "row_limit":        int(row_limit),
        **normalized,
    }


def generate_sql(query, db_info):
    """Execute query via the optimized /query/fast-analyze backend endpoint."""
    normalized = normalize_db_info(db_info)
    if not normalized:
        return {"success": False, "error": "Missing connection details."}
    try:
        from utils.settings_manager import get_setting
        payload = _build_fast_analyze_payload(query, db_info)
        raw_chart = get_setting("chart_preference")
        chart_preference = "Auto" if "Auto" in raw_chart else raw_chart.replace(" Chart", "").replace(" Plot", "")
        response = requests.post(
            f"{BASE_URL}/query/fast-analyze",
            json=payload,
            headers=get_headers(),
            timeout=90,
        )
        parsed = _parse_response(response)
        if not parsed.get("success"):
            return {"success": False, "error": parsed.get("error") or parsed.get("message", "Analysis failed")}
        rows = parsed.get("rows", [])
        columns = parsed.get("columns", [])
        recommended_chart = parsed.get("recommended_chart")
        if chart_preference and chart_preference != "Auto":
            recommended_chart = chart_preference.lower()
        return {
            "success":             True,
            "sql":                 parsed.get("sql", ""),
            "explanation":         parsed.get("explanation") or "",
            "data":                rows,
            "columns":             columns,
            "row_count":           parsed.get("row_count", len(rows)),
            "recommended_chart":   recommended_chart,
            "chart_justification": parsed.get("chart_justification", ""),
            "insight_cards":       parsed.get("insight_cards", []),
            "narrative":           parsed.get("narrative"),
            "confidence_score":    parsed.get("confidence_score"),
            "confidence_label":    parsed.get("confidence_label"),
            "ambiguities":         parsed.get("ambiguities", []),
            "warnings":            parsed.get("warnings", []),
            "execution_duration":  parsed.get("execution_duration", 0.0),
            "complexity":          parsed.get("complexity"),
            "cache_hit":           parsed.get("cache_hit", False),
            "timing":              parsed.get("timing", {}),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def stream_analyze(query: str, db_info: dict):
    """
    Progressive SSE streaming generator.
    Yields (event_type: str, data: dict) tuples as each pipeline stage completes.

    Events in order:
      stage_update      — animated status message (classifying/generating/executing/analyzing)
      sql_ready         — SQL generated  → show SQL preview IMMEDIATELY
      data_ready        — SQL executed   → show results table IMMEDIATELY
      explanation_ready — AI explanation → update SQL preview in-place
      insights_ready    — AI insights   → show insight cards IMMEDIATELY
      complete          — chart + totals → show chart + export buttons
      error             — any failure
    """
    normalized = normalize_db_info(db_info)
    if not normalized:
        yield "error", {"message": "Missing connection details. Please connect first."}
        return
    try:
        payload = _build_fast_analyze_payload(query, db_info)
        headers = dict(get_headers())
        headers["Accept"] = "text/event-stream"
        with requests.post(
            f"{BASE_URL}/query/stream-analyze",
            json=payload,
            headers=headers,
            stream=True,
            timeout=120,
        ) as resp:
            if resp.status_code == 401:
                yield "error", {"message": "Session expired. Please log in again."}
                return
            if resp.status_code >= 400:
                yield "error", {"message": f"Backend error HTTP {resp.status_code}."}
                return
            event_type = None
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:") and event_type:
                    try:
                        yield event_type, json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        pass
    except requests.exceptions.Timeout:
        yield "error", {"message": "Request timed out. Try a simpler question."}
    except requests.exceptions.ConnectionError:
        yield "error", {"message": "Cannot connect to backend on port 8000."}
    except Exception as exc:
        yield "error", {"message": f"Streaming error: {exc}"}


# ─── Premium AI Features ──────────────────────────────────────────────────────

def optimize_query(
    sql: str,
    user_query: str,
    dialect: str = "sqlite",
    schema_context: str = None,
    execution_ms: float = None,
) -> dict:
    """✨ Optimize Query — Nemotron 120B deep SQL analysis.

    Returns optimized SQL, bottleneck analysis, index recommendations,
    and intelligent follow-up query suggestions.
    """
    payload = {
        "sql":        sql,
        "user_query": user_query,
        "dialect":    dialect,
    }
    if schema_context:
        payload["schema_context"] = schema_context
    if execution_ms is not None:
        payload["execution_ms"] = execution_ms

    try:
        resp = requests.post(
            f"{BASE_URL}/query/optimize",
            headers=get_headers(),
            json=payload,
            timeout=90,  # intentionally generous — deep reasoning is slow
        )
        return _parse_response(resp)
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Optimization timed out. Try again."}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to backend."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _sanitize_nan(obj):
    import math
    try:
        import numpy as np
        has_np = True
    except ImportError:
        has_np = False

    if isinstance(obj, dict):
        return {k: _sanitize_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_nan(x) for x in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif has_np:
        if isinstance(obj, (np.float64, np.float32)):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif obj is np.nan:
            return None
    return obj


def generate_report(
    sql: str,
    user_query: str,
    columns: list = None,
    rows: list = None,
    explanation: str = None,
) -> dict:
    """📄 Generate Business Report — GPT-OSS 120B professional report.

    Returns a structured markdown business report with executive summary,
    key insights, business observations, and recommended actions.
    """
    payload = {
        "sql":        sql,
        "user_query": user_query,
        "columns":    columns or [],
        "rows":       _sanitize_nan(rows or []),
    }
    if explanation:
        payload["explanation"] = explanation

    try:
        resp = requests.post(
            f"{BASE_URL}/query/generate-report",
            headers=get_headers(),
            json=payload,
            timeout=120,  # intentionally generous — long-form report generation
        )
        return _parse_response(resp)
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Report generation timed out. Try again."}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to backend."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


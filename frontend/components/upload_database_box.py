import streamlit as st

from services.api_client import upload_database
from utils.db_context import load_database_context
from utils.icons import get_icon


def render_upload_database_box():
    st.markdown("""
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.db-upload-card-marker) {
        background: linear-gradient(135deg, rgba(15,23,42,0.95), rgba(30,41,59,0.8)) !important;
        border: 1px solid rgba(99,102,241,0.25) !important;
        border-radius: 16px !important;
        padding: 28px 28px 24px 28px !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.03) !important;
        margin-top: 8px !important;
    }
    /* Reset outer container if nested to prevent card-inside-card bug */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div[data-testid="stVerticalBlockBorderWrapper"] .db-upload-card-marker) {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }
    .upload-hero {
        text-align: center;
        padding: 16px 0 8px 0;
    }
    .upload-header-row {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 4px;
    }
    .upload-header-icon-pill {
        color: #8B5CF6;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .upload-icon-circle {
        background: linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.05));
        border: 2px dashed rgba(99,102,241,0.25);
        border-radius: 16px;
        padding: 28px;
        text-align: center;
        margin: 12px 0;
        transition: all 0.2s ease;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }
    .upload-main-icon {
        color: #6366F1;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .upload-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #E2E8F0;
    }
    .upload-subtitle {
        font-size: 0.82rem;
        color: #64748B;
    }
    .desktop-desc { display: inline; }
    .mobile-desc { display: none; }
    .upload-badge-row {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        justify-content: flex-start;
        margin: 10px 0 14px 0;
    }
    .upload-badge {
        background: rgba(99,102,241,0.1);
        border: 1px solid rgba(99,102,241,0.25);
        border-radius: 6px;
        padding: 3px 10px;
        font-size: 0.75rem;
        color: #A78BFA;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 5px;
    }

    /* Hide Streamlit default file list and pagination to prevent repetition */
    [data-testid="stFileUploaderUploadedFiles"],
    [data-testid="stFileUploaderPagination"],
    .stFileUploaderFile,
    .uploadedFiles {
        display: none !important;
    }

    /* Style for our custom file grid container cards */
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) {
        background-color: rgba(30, 41, 59, 0.45) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 10px !important;
        padding: 6px 10px !important;
        margin: 2px 0 !important;
        transition: all 0.2s ease-in-out !important;
    }
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker):hover {
        border-color: rgba(139, 92, 246, 0.3) !important;
        background-color: rgba(30, 41, 59, 0.65) !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
    }

    /* Style the vertical block and button container inside the columns */
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="column"] [data-testid="stVerticalBlock"] {
        gap: 0px !important;
        margin: 0 !important;
        padding: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="column"]:first-child [data-testid="stVerticalBlock"] {
        align-items: flex-start !important;
    }
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="column"]:last-child [data-testid="stVerticalBlock"] {
        align-items: flex-end !important;
    }

    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="stButton"] {
        margin: 0 !important;
        padding: 0 !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 24px !important;
        height: 24px !important;
    }

    /* Style the delete button inside our custom file card container */
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="stButton"] button {
        height: 24px !important;
        width: 24px !important;
        min-width: 24px !important;
        padding: 0 !important;
        border-radius: 50% !important;
        background-color: transparent !important;
        color: #94A3B8 !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 0.75rem !important;
        line-height: 1 !important;
        margin: 0 !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="stButton"] button:hover {
        background-color: rgba(244, 63, 94, 0.15) !important;
        color: #F43F5E !important;
        border-color: #F43F5E !important;
    }

    /* Create one stable custom wrapper around the entire file card using display: contents to flatten Streamlit's inner divs */
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) {
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        min-height: 72px !important;
        width: 100% !important;
        padding: 12px 16px !important;
        box-sizing: border-box !important;
    }

    /* Flatten all intermediate Streamlit wrappers so they disappear from the flex layout */
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) > div,
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="stVerticalBlock"],
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="stHorizontalBlock"],
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="stElementContainer"] {
        display: contents !important;
    }

    /* Prevent hidden spacing by resetting margin for all nested elements */
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) * {
        margin: 0 !important;
    }

    /* Override the stColumn wrapper so it properly aligns its inner contents */
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="stColumn"] {
        display: flex !important;
        align-items: center !important;
        min-width: 0 !important; /* prevent overflow */
    }
    
    /* Left column (file info section) */
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="stColumn"]:first-child {
        flex: 1 1 auto !important;
        justify-content: flex-start !important;
    }
    
    /* Right column (delete button section) */
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) [data-testid="stColumn"]:last-child {
        flex: 0 0 auto !important;
        justify-content: flex-end !important;
    }

    /* Hide the marker elements */
    .custom-file-card-marker {
        display: none !important;
    }

    /* ── Responsive Upload Box ── */
    @media (max-width: 768px) {
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.db-upload-card-marker) {
            padding: 20px 16px 16px 16px !important;
            border-radius: 12px !important;
        }
        .upload-title { font-size: 0.95rem !important; }
        .upload-subtitle { font-size: 0.76rem !important; }
        .desktop-desc { display: none !important; }
        .mobile-desc { display: inline !important; }
        .upload-badge-row {
            flex-wrap: wrap !important;
            gap: 6px !important;
            margin: 8px 0 10px 0 !important;
        }
        .upload-badge { font-size: 0.7rem !important; padding: 2px 8px !important; }
    }
    @media (max-width: 480px) {
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.db-upload-card-marker) {
            padding: 16px 12px 12px 12px !important;
            border-radius: 10px !important;
        }
        .upload-title { font-size: 0.78rem !important; }
        .upload-subtitle { font-size: 0.68rem !important; margin-bottom: 8px !important; }
        .upload-badge { font-size: 0.6rem !important; padding: 1px 4px !important; }
        [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"]:has(.custom-file-card-marker) {
            padding: 4px 6px !important;
            border-radius: 8px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    db_badge_icon = get_icon("database", size=11, color="#A78BFA")
    file_badge_icon = get_icon("folder", size=11, color="#A78BFA")

    with st.container(border=True):
        st.markdown("<div class='db-upload-card-marker'></div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class='upload-header-row'>
            <div class='upload-title'>Import Your Data</div>
        </div>
        <div class='upload-subtitle' style='padding-left: 0;'>
            <span class='desktop-desc'>Drop your SQLite, CSV, or SQL script files — the engine ingests, indexes, and makes them instantly queryable by AI.</span>
            <span class='mobile-desc'>Drop SQLite, CSV, or SQL files to instantly query with AI.</span>
        </div>
        <div class='upload-badge-row'>
            <span class='upload-badge'>{db_badge_icon} SQLite (.db)</span>
            <span class='upload-badge'>{file_badge_icon} CSV</span>
            <span class='upload-badge'>{db_badge_icon} .sqlite3</span>
            <span class='upload-badge'>{file_badge_icon} SQL (.sql)</span>
        </div>
        """, unsafe_allow_html=True)

        uploaded_files = st.file_uploader(
            "Drop your database files here",
            type=["sqlite", "db", "sqlite3", "csv", "sql"],
            help="CSV or SQL script files are imported and set up automatically.",
            label_visibility="collapsed",
            accept_multiple_files=True,
        )

        # Initialize state
        if "deleted_files" not in st.session_state:
            st.session_state["deleted_files"] = set()
        if "last_uploader_filenames" not in st.session_state:
            st.session_state["last_uploader_filenames"] = set()

        active_files = []
        if uploaded_files:
            current_uploader_filenames = {f.name for f in uploaded_files}
            
            # If the set of files in uploader has changed, sync deleted_files
            if current_uploader_filenames != st.session_state["last_uploader_filenames"]:
                added_files = current_uploader_filenames - st.session_state["last_uploader_filenames"]
                st.session_state["deleted_files"] -= added_files
                st.session_state["last_uploader_filenames"] = current_uploader_filenames

            active_files = [f for f in uploaded_files if f.name not in st.session_state["deleted_files"]]
        else:
            st.session_state["deleted_files"] = set()
            st.session_state["last_uploader_filenames"] = set()

        if active_files:
            st.write("")  # small spacing
            cols = st.columns(3)
            for idx, f in enumerate(active_files):
                col = cols[idx % 3]
                with col:
                    with st.container(border=True):
                        st.markdown("<div class='custom-file-card-marker'></div>", unsafe_allow_html=True)
                        info_col, btn_col = st.columns([5, 1])
                        with info_col:
                            size_kb = f.size / 1024
                            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
                            is_csv = f.name.lower().endswith(".csv")
                            icon_type = "folder" if is_csv else "database"
                            icon_color = "#A78BFA" if is_csv else "#60A5FA"
                            file_icon_svg = get_icon(icon_type, size=14, color=icon_color)
                            st.markdown(f"""
                            <div style='display:flex; align-items:center; gap:8px; overflow:hidden;'>
                                <div style='flex-shrink:0; display:flex; align-items:center;'>{file_icon_svg}</div>
                                <div style='display:flex; flex-direction:column; overflow:hidden; min-width:0;'>
                                    <span style='color:#E2E8F0; font-weight:500; font-size:0.8rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:block;' title='{f.name}'>
                                        {f.name}
                                    </span>
                                    <span style='color:#64748B; font-size:0.7rem;'>{size_str}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        with btn_col:
                            if st.button("✕", key=f"del_{f.name}_{idx}", help=f"Remove {f.name}"):
                                st.session_state["deleted_files"].add(f.name)
                                st.rerun()

            st.write("")  # spacing before button

            if st.button("Connect & Analyze", type="primary", use_container_width=True):
                if not st.session_state.get("access_token"):
                    st.error("Please log in first before uploading databases.")
                    return

                with st.spinner("Uploading and connecting..."):
                    result = upload_database(active_files)

                if not result.get("success"):
                    st.error(result.get("message", "Upload failed."))
                    return

                data = result.get("data") or {}
                import re as _re

                raw_name = data.get("source_filename") or data.get("database") or ", ".join([f.name for f in active_files])
                
                # Smart clean: split by " & ", clean each part, then join
                db_display_name = data.get("database") or "Dataset"
                parts = db_display_name.split(" & ")
                cleaned_parts = []
                for part in parts:
                    if _re.match(r"^\d+\s+more$", part.strip(), flags=_re.IGNORECASE):
                        cleaned_parts.append(part.strip())
                        continue
                    clean = _re.split(r"[/\\]", str(part))[-1]
                    clean = _re.sub(r"\.(db|sqlite|sqlite3|csv)$", "", clean, flags=_re.IGNORECASE)
                    clean = _re.sub(r"^\d+\s+", "", clean.replace("_", " ").replace("-", " ")).strip()
                    cleaned_parts.append(clean.title() if clean else part)
                display_name = " & ".join(cleaned_parts)

                db_info = {
                    "database_type":   "sqlite",
                    "file_path":       data.get("file_path"),
                    "database":        display_name,
                    "host":            data.get("host", "local"),
                    "port":            data.get("port", 0),
                    "username":        data.get("username", "sqlite"),
                    "password":        "",
                    "source_filename": raw_name,
                }
                st.session_state["connected"] = True
                st.session_state["db_info"]   = db_info

                with st.spinner("Validating tables, columns & schema…"):
                    ok, msg = load_database_context(db_info, force_refresh=True)

                if ok:
                    # Save SQLite connection to connection history
                    try:
                        from utils.connection_manager import save_connection, save_active_session
                        save_connection(
                            host=db_info["host"],
                            port=int(db_info["port"]),
                            username=db_info["username"],
                            database=db_info["database"],
                            database_type="sqlite",
                            file_path=db_info.get("file_path"),
                            source_filename=db_info.get("source_filename"),
                        )
                        # Also persist the full session for refresh restore
                        _uname = st.session_state.get("user_profile", {}).get("username", "default")
                        save_active_session(_uname, db_info)
                    except Exception:
                        pass

                    try:
                        from utils.settings_manager import log_activity
                        log_activity(f"Uploaded and connected to database: '{display_name}' (SQLITE)")
                    except Exception:
                        pass

                    table_count = st.session_state.get("db_stats", {}).get(
                        "table_count",
                        len(st.session_state.get("schema_data") or {}),
                    )
                    st.success(
                        f"✅ **{display_name}** connected — "
                        f"{table_count} table{'s' if table_count != 1 else ''} validated successfully."
                    )
                    st.rerun()
                else:
                    st.session_state["connected"] = False
                    st.error(f"Uploaded but schema validation failed: {msg}")



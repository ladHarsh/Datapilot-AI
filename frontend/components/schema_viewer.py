import streamlit as st
from utils.icons import get_icon
import re


def _clean_db_name(raw: str) -> str:
    """Strip file-system paths and return a clean, human-readable dataset name."""
    if not raw:
        return "Dataset"
    # Remove any path separators and common backend path fragments
    name = re.split(r"[/\\]", raw)[-1]
    # Remove extensions
    name = re.sub(r"\.(db|sqlite|sqlite3|csv)$", "", name, flags=re.IGNORECASE)
    # Replace underscores/hyphens with spaces and title-case
    name = name.replace("_", " ").replace("-", " ").strip()
    # Remove numeric prefix like "1 " or "123 " that come from upload IDs
    name = re.sub(r"^\d+\s+", "", name)
    return name.title() if name else "Dataset"


def render_schema_viewer():
    st.markdown("""
    <style>
    .schema-card {
        background: linear-gradient(135deg, rgba(15,23,42,0.95), rgba(11,17,32,0.95));
        border: 1px solid rgba(99,102,241,0.18);
        border-radius: 14px;
        padding: 14px 14px 10px 14px;
        margin-bottom: 8px;
    }
    .schema-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 10px;
    }
    .schema-icon {
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .schema-title {
        font-size: 0.9rem;
        font-weight: 700;
        color: #E2E8F0;
        flex: 1;
    }
    .schema-count-badge {
        background: rgba(99,102,241,0.15);
        border: 1px solid rgba(99,102,241,0.3);
        border-radius: 10px;
        padding: 1px 8px;
        font-size: 0.7rem;
        color: #A78BFA;
        font-weight: 600;
    }
    .schema-dataset-chip {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: rgba(16,185,129,0.1);
        border: 1px solid rgba(16,185,129,0.25);
        border-radius: 20px;
        padding: 3px 10px;
        font-size: 0.72rem;
        color: #10B981;
        font-weight: 600;
        margin-bottom: 10px;
    }
    /* Fixed-height scrollable schema body — page does NOT scroll */
    .schema-scroll-body {
        max-height: 420px;
        overflow-y: auto;
        overflow-x: hidden;
        padding-right: 4px;
    }
    .schema-scroll-body::-webkit-scrollbar { width: 4px; }
    .schema-scroll-body::-webkit-scrollbar-track { background: transparent; }
    .schema-scroll-body::-webkit-scrollbar-thumb {
        background: rgba(99,102,241,0.35);
        border-radius: 2px;
    }
    .schema-table-block {
        background: rgba(30,41,59,0.6);
        border: 1px solid rgba(51,65,85,0.5);
        border-radius: 10px;
        padding: 8px 10px;
        margin-bottom: 8px;
    }
    .schema-table-name {
        font-size: 0.82rem;
        font-weight: 700;
        color: #8B5CF6;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .schema-col-row {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 2px 0;
        font-size: 0.76rem;
    }
    .schema-col-dot {
        width: 4px; height: 4px;
        background: #475569;
        border-radius: 50%;
        flex-shrink: 0;
    }
    .schema-col-name {
        color: #CBD5E1;
        font-weight: 500;
        flex: 1;
    }
    .schema-col-type {
        color: #475569;
        font-size: 0.68rem;
        font-family: 'JetBrains Mono', monospace;
    }
    .schema-key-badge {
        background: rgba(245,158,11,0.15);
        border: 1px solid rgba(245,158,11,0.3);
        border-radius: 3px;
        padding: 0px 4px;
        font-size: 0.6rem;
        color: #F59E0B;
        font-weight: 700;
    }
    .schema-empty-state {
        text-align: center;
        padding: 32px 16px;
        color: #475569;
    }

    /* ── Responsive Schema Viewer ── */
    @media (max-width: 768px) {
        .schema-card {
            padding: 10px 10px 8px 10px !important;
            border-radius: 12px !important;
        }
        .schema-scroll-body {
            max-height: 280px !important;
        }
        .schema-header { margin-bottom: 8px !important; }
        .schema-title { font-size: 0.82rem !important; }
        .schema-count-badge { font-size: 0.65rem !important; padding: 1px 6px !important; }
        .schema-dataset-chip { font-size: 0.68rem !important; padding: 2px 8px !important; }
        .schema-table-block { padding: 6px 8px !important; margin-bottom: 6px !important; }
        .schema-table-name { font-size: 0.76rem !important; margin-bottom: 4px !important; }
        .schema-col-row { font-size: 0.72rem !important; }
        .schema-col-type { font-size: 0.62rem !important; }
    }
    @media (max-width: 480px) {
        .schema-scroll-body { max-height: 180px !important; }
        .schema-card { padding: 8px 8px 6px 8px !important; }
        .schema-title { font-size: 0.78rem !important; }
        .schema-table-name { font-size: 0.72rem !important; margin-bottom: 2px !important; }
        .schema-col-row { font-size: 0.68rem !important; padding: 1px 0 !important; }
        .schema-col-type { font-size: 0.6rem !important; }
        .schema-col-dot { width: 3px !important; height: 3px !important; }
        .schema-key-badge { font-size: 0.55rem !important; padding: 0 2px !important; }
        .schema-count-badge { font-size: 0.6rem !important; padding: 1px 4px !important; }
        .schema-dataset-chip { font-size: 0.62rem !important; padding: 1px 6px !important; margin-bottom: 6px !important; }
    }
    @media (max-width: 375px) {
        .schema-scroll-body { max-height: 150px !important; }
    }
    </style>
    """, unsafe_allow_html=True)

    if not st.session_state.get("connected"):
        plug_svg = get_icon("database", size=28, color="#334155")
        st.markdown(f"""
        <div class='schema-card'>
            <div class='schema-empty-state'>
                <div style='margin-bottom:10px;'>{plug_svg}</div>
                <div style='font-size:0.85rem; font-weight:600; color:#64748B;'>Schema Explorer</div>
                <div style='font-size:0.78rem; color:#475569; margin-top:4px;'>Connect a database to explore tables &amp; columns</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    if st.session_state.get("schema_load_error"):
        st.error(st.session_state["schema_load_error"])
        return

    if not st.session_state.get("schema_loaded"):
        st.info("Loading schema…")
        return

    schema_data = st.session_state.get("schema_data") or {}
    if not schema_data:
        st.warning("No tables found in this database.")
        return

    raw = st.session_state.get("schema_raw", {})
    table_count = raw.get("table_count", len(schema_data))

    # Get clean display name — never expose file paths
    db_info = st.session_state.get("db_info", {})
    raw_db_name = (
        db_info.get("source_filename")
        or db_info.get("database")
        or raw.get("database")
        or "Dataset"
    )
    clean_name = _clean_db_name(str(raw_db_name))

    explorer_icon_svg = get_icon("database", size=14, color="#8B5CF6", stroke_width=2.0)
    key_icon_svg = get_icon("key", size=9, color="#F59E0B")

    # Build scrollable HTML table blocks
    blocks_html = ""
    for table_name, columns in schema_data.items():
        col_rows_html = ""
        for col in columns:
            key_badge = "<span class='schema-key-badge'>PK</span>" if col.get("key") else ""
            col_rows_html += (
                f"<div class='schema-col-row'>"
                f"<span class='schema-col-dot'></span>"
                f"<span class='schema-col-name'>{col['name']}</span>"
                f"<span class='schema-col-type'>{col['type']}</span>"
                f"{key_badge}</div>"
            )
        blocks_html += (
            f"<div class='schema-table-block'>"
            f"<div class='schema-table-name'>🔷 {table_name} "
            f"<span style='color:#475569; font-weight:400; font-size:0.7rem;'>({len(columns)} cols)</span></div>"
            f"{col_rows_html}</div>"
        )

    st.markdown(f"""
    <div class='schema-card'>
        <div class='schema-header'>
            <span class='schema-icon'>{explorer_icon_svg}</span>
            <span class='schema-title'>Schema Explorer</span>
            <span class='schema-count-badge'>{table_count} tables</span>
        </div>
        <div class='schema-dataset-chip'>{clean_name}</div>
        <div class='schema-scroll-body'>
            {blocks_html}
        </div>
    </div>
    """, unsafe_allow_html=True)

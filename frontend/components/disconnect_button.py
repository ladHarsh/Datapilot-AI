"""
Disconnect Button — DataPilot AI
Clean styled disconnect with safe session reset.
"""
import re
import streamlit as st
from utils.icons import get_icon


def _clean_db_name(db_info: dict) -> str:
    raw = (
        db_info.get("source_filename")
        or db_info.get("database")
        or "Dataset"
    )
    name = re.split(r"[/\\]", str(raw))[-1]
    name = re.sub(r"\.(db|sqlite|sqlite3|csv)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^\d+\s+", "", name.replace("_", " ").replace("-", " ")).strip()
    return name.title() if name else "Dataset"


def render_disconnect_button():
    db_info = st.session_state.get("db_info", {})
    db_type = db_info.get("database_type", db_info.get("db_type", "")).lower() or "db"
    display_type = "FILE" if db_type in ("sqlite", "sqlite3", "file") else db_type.upper()
    display_name = _clean_db_name(db_info)

    st.markdown("""
    <style>
    /* Hide marker container completely so it doesn't take up space */
    div.element-container:has(.disconnect-row-anchor) {
        display: none !important;
        margin: 0 !important;
        padding: 0 !important;
        height: 0 !important;
    }

    /* Pull the active database row up to remove the blank space above it */
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"],
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock {
        margin-top: -24px !important;
        margin-bottom: 4px !important;
    }
    
    /* Vertically center the contents of both columns */
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] > div,
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock > div {
        display: flex !important;
        align-items: center !important;
    }

    /* Force the vertical blocks inside active database column to align to left */
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] > div:first-child div[data-testid="stVerticalBlock"],
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock > div:first-child div.stVerticalBlock {
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: flex-start !important;
        gap: 0 !important;
        height: 100% !important;
    }

    /* Force the vertical blocks inside disconnect button column to align to right */
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] > div:last-child div[data-testid="stVerticalBlock"],
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock > div:last-child div.stVerticalBlock {
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: flex-end !important;
        gap: 0 !important;
        height: 100% !important;
    }

    /* Reset margins and paddings for all wrapper containers in these columns to avoid offsets */
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] div.element-container,
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock div.element-container {
        margin: 0 !important;
        padding: 0 !important;
    }

    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] div.stMarkdown,
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] div[data-testid="stMarkdownContainer"],
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock div.stMarkdown,
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock div[data-testid="stMarkdownContainer"] {
        margin: 0 !important;
        padding: 0 !important;
    }

    .active-db-bar {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(16,185,129,0.07);
        border: 1px solid rgba(16,185,129,0.2);
        border-radius: 8px;
        padding: 0 14px;
        margin-bottom: 0px;
        height: 38px;
        box-sizing: border-box;
        width: fit-content;
    }
    .active-db-dot {
        width: 8px; height: 8px;
        background: #10B981; border-radius: 50%;
        box-shadow: 0 0 6px rgba(16,185,129,0.6);
        flex-shrink: 0;
        animation: pulse-green-bar 2s infinite;
    }
    @keyframes pulse-green-bar {
        0%, 100% { box-shadow: 0 0 4px rgba(16,185,129,0.4); }
        50%       { box-shadow: 0 0 8px rgba(16,185,129,0.8); }
    }
    .active-db-name {
        font-size: 0.85rem;
        font-weight: 700;
        color: #10B981;
        flex: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .active-db-type {
        font-size: 0.72rem;
        color: #64748B;
        background: rgba(15,23,42,0.6);
        border: 1px solid #1E293B;
        border-radius: 5px;
        padding: 2px 8px;
        line-height: 1.4;
    }
    
    /* Reset margins and paddings for stButton wrapper to avoid offsets */
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] [data-testid="stButton"],
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock [data-testid="stButton"] {
        margin: 0 !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 38px !important;
        min-height: 38px !important;
        width: 100% !important;
    }

    /* Target the Disconnect button in this block using a robust selector */
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] [data-testid="stButton"] button,
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock [data-testid="stButton"] button {
        background: rgba(220, 38, 38, 0.04) !important;
        border: 1px solid rgba(239, 68, 68, 0.18) !important;
        color: #F87171 !important;
        border-radius: 8px !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.2px !important;
        padding: 0 16px !important;
        height: 38px !important;
        min-height: 38px !important;
        line-height: 1 !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin: 0 !important;
        width: 100% !important;
        box-sizing: border-box !important;
        backdrop-filter: blur(8px) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.03) !important;
    }

    /* Prepend custom futuristic broken circuit / power icon */
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] [data-testid="stButton"] button::before,
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock [data-testid="stButton"] button::before {
        content: "";
        display: inline-block;
        width: 13px;
        height: 13px;
        margin-right: 7px;
        background-repeat: no-repeat;
        background-size: contain;
        background-position: center;
        /* Custom Neon Crimson power vector */
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23F87171' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><path d='M18.36 6.64a9 9 0 1 1-12.73 0'></path><line x1='12' y1='2' x2='12' y2='12'></line></svg>");
        vertical-align: middle;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        opacity: 0.85;
    }

    /* Hover State with Neon Glow, Crimson BG, Scale & Soft Shadows */
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] [data-testid="stButton"] button:hover,
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock [data-testid="stButton"] button:hover {
        background: rgba(220, 38, 38, 0.15) !important;
        border-color: rgba(248, 113, 113, 0.45) !important;
        color: #FFFFFF !important;
        box-shadow: 0 0 16px rgba(239, 68, 68, 0.22), 0 4px 12px rgba(0, 0, 0, 0.25), inset 0 0 8px rgba(239, 68, 68, 0.1) !important;
        transform: translateY(-1px) !important;
    }

    /* Switch icon stroke to pure high-glow white on hover and twist */
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] [data-testid="stButton"] button:hover::before,
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock [data-testid="stButton"] button:hover::before {
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FFFFFF' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><path d='M18.36 6.64a9 9 0 1 1-12.73 0'></path><line x1='12' y1='2' x2='12' y2='12'></line></svg>");
        opacity: 1;
        transform: rotate(90deg); /* Futuristic system twist animation */
    }

    /* Active click compression state */
    div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] [data-testid="stButton"] button:active,
    div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock [data-testid="stButton"] button:active {
        transform: translateY(0) scale(0.99) !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2) !important;
    }

    /* ── Responsive Disconnect Button ── */
    @media (max-width: 768px) {
        div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"],
        div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock {
            margin-top: -12px !important;
            flex-wrap: wrap !important;
        }
        div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] > div,
        div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock > div {
            flex: 1 1 100% !important;
            max-width: 100% !important;
            min-width: 100% !important;
        }
        .active-db-bar {
            width: 100% !important;
            justify-content: flex-start !important;
        }
        div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] [data-testid="stButton"] button,
        div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock [data-testid="stButton"] button {
            height: 36px !important;
            min-height: 36px !important;
            font-size: 0.78rem !important;
            margin-top: 6px !important;
        }
    }
    @media (max-width: 480px) {
        .active-db-bar {
            height: 32px !important;
            padding: 0 10px !important;
        }
        .active-db-name {
            font-size: 0.76rem !important;
        }
        .active-db-type {
            font-size: 0.64rem !important;
            padding: 1px 6px !important;
        }
        .active-db-dot {
            width: 6px !important;
            height: 6px !important;
        }
        div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] [data-testid="stButton"] button,
        div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock [data-testid="stButton"] button {
            height: 32px !important;
            min-height: 32px !important;
            font-size: 0.74rem !important;
            margin-top: 4px !important;
        }
        div.element-container:has(.disconnect-row-anchor) + div.element-container div[data-testid="stHorizontalBlock"] [data-testid="stButton"] button::before,
        div.element-container:has(.disconnect-row-anchor) + div.element-container div.stHorizontalBlock [data-testid="stButton"] button::before {
            width: 11px !important;
            height: 11px !important;
            margin-right: 5px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='disconnect-row-anchor'></div>", unsafe_allow_html=True)
    col_info, col_btn = st.columns([4, 1])
    with col_info:
        st.markdown(f"""
        <div class='active-db-bar'>
            <div class='active-db-dot'></div>
            <div class='active-db-name'>{display_name}</div>
            <span class='active-db-type'>{display_type}</span>
        </div>
        """, unsafe_allow_html=True)
    with col_btn:
        if st.button("Disconnect", key="disconnect_btn", use_container_width=True):
            try:
                from utils.settings_manager import log_activity
                log_activity(f"Disconnected from database: '{display_name}'")
            except Exception:
                pass

            try:
                from utils.connection_manager import clear_active_session
                _uname = st.session_state.get("user_profile", {}).get("username", "default")
                clear_active_session(_uname)
            except Exception:
                pass

            for key in [
                "connected", "db_info", "current_query", "schema_data",
                "schema_raw", "schema_loaded", "schema_load_error",
                "db_stats", "query_suggestions", "last_result",
                "_connection_restored", "_token_refreshed", "query_history",
            ]:
                if key in ["connected", "schema_loaded", "_connection_restored", "_token_refreshed"]:
                    st.session_state[key] = False
                elif key in ["db_info", "schema_raw", "db_stats"]:
                    st.session_state[key] = {}
                elif key in ["current_query", "generated_sql"]:
                    st.session_state[key] = ""
                elif key in ["schema_data", "last_result", "schema_load_error"]:
                    st.session_state[key] = None
                elif key in ["query_suggestions", "query_history"]:
                    st.session_state[key] = []
            st.rerun()

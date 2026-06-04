import streamlit as st

from utils.session_manager import initialize_session

from pages.login import show_login
from pages.dashboard import show_dashboard
from pages.query_history import show_query_history
from pages.settings import show_settings



# ---------------- PAGE CONFIG ---------------- #

st.set_page_config(
    page_title="DataPilot AI",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ---------------- HIDE STREAMLIT DEFAULT PAGES ---------------- #

hide_streamlit_style = """
<style>

/* Hide default Streamlit multipage navigation */
[data-testid="stSidebarNav"] {
    display: none;
}

/* Make header transparent so the sidebar toggle arrow is visible, while hiding deploy buttons */
header[data-testid="stHeader"] {
    background-color: transparent !important;
    z-index: 99999 !important;
}
header[data-testid="stHeader"] [data-testid="stHeaderContent"],
header[data-testid="stHeader"] [data-testid="stDeployButton"] {
    display: none !important;
}

/* Sidebar collapse/expand button premium styling */
button[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedSidebarNoOverlay"] button {
    background-color: rgba(30, 41, 59, 0.7) !important;
    border: 1px solid rgba(99, 102, 241, 0.3) !important;
    border-radius: 8px !important;
    color: #F1F5F9 !important;
    transition: all 0.2s ease !important;
}
button[data-testid="stSidebarCollapseButton"]:hover,
[data-testid="collapsedSidebarNoOverlay"] button:hover {
    background-color: rgba(99, 102, 241, 0.2) !important;
    border-color: rgba(99, 102, 241, 0.6) !important;
    transform: scale(1.05);
}

</style>
"""

st.markdown(
    hide_streamlit_style,
    unsafe_allow_html=True
)


# ---------------- SESSION INIT ---------------- #

initialize_session()

# Restore authentication from query params
if st.query_params.get("auth") == "true":

    st.session_state["authenticated"] = True
    if "user_profile" not in st.session_state or not st.session_state["user_profile"]:
        st.session_state["user_profile"] = {
            "username": st.query_params.get("user", "admin"),
            "role": st.query_params.get("role", "admin")
        }
    if "access_token" not in st.session_state and "token" in st.query_params:
        st.session_state["access_token"] = st.query_params.get("token")

    # Restore current page from query params (so refresh keeps you on the same page)
    _valid_pages = {"Dashboard", "Settings", "Profile", "Query History", "Recent Connections"}
    _page_from_url = st.query_params.get("page", "")
    if _page_from_url in _valid_pages and not st.session_state.get("_fresh_login"):
        st.session_state["menu"] = _page_from_url

# ── Restore persisted settings & query history on every fresh load ── #
if st.session_state.get("authenticated"):
    from utils.settings_manager import load_settings_from_file
    _username = st.session_state.get("user_profile", {}).get("username", "")
    _is_fresh_login = st.session_state.get("_fresh_login", False)

    # Clear the fresh-login flag after reading it (only skip restore on the first rerun)
    if _is_fresh_login:
        st.session_state["_fresh_login"] = False
        # Mark all restore steps as done so they don't run later in this session
        st.session_state["_token_refreshed"] = True
        st.session_state["_settings_loaded"] = False   # still load settings
        st.session_state["_history_loaded"] = False    # still load history
        st.session_state["_connection_restored"] = True  # SKIP DB restore on fresh login

    # ── Step 1: Silently re-login to get a fresh JWT token (expires every 7 days) ── #
    if not st.session_state.get("_token_refreshed"):
        st.session_state["_token_refreshed"] = True
        if not st.session_state.get("access_token"):
            try:
                from utils.connection_manager import load_auth_credentials, load_any_auth_credentials
                from services.auth_client import login_user
                creds = load_auth_credentials(_username) or load_any_auth_credentials()
                if creds:
                    res = login_user(creds["username"], creds["password"])
                    if res.get("success"):
                        _refreshed_user = res.get("user", {})
                        st.session_state["user_profile"] = _refreshed_user
                        _username = _refreshed_user.get("username", _username)
                        # Update query params with fresh token
                        if st.session_state.get("access_token"):
                            st.query_params["token"] = st.session_state["access_token"]
            except Exception:
                pass

    # ── Step 2: Restore settings from disk ── #
    if not st.session_state.get("_settings_loaded"):
        load_settings_from_file(_username)
        st.session_state["_settings_loaded"] = True

    # ── Step 3: Restore query history from backend ── #
    if not st.session_state.get("_history_loaded"):
        if not st.session_state.get("query_history"):
            try:
                from services.api_client import fetch_query_history
                loaded = fetch_query_history(limit=30)
                if loaded:
                    st.session_state["query_history"] = loaded
            except Exception:
                pass
        st.session_state["_history_loaded"] = True

    # ── Step 4: Restore active database connection (only on page refresh, not fresh login) ── #
    if not st.session_state.get("_connection_restored"):
        st.session_state["_connection_restored"] = True
        if not st.session_state.get("connected") and st.session_state.get("access_token"):
            try:
                from utils.connection_manager import load_active_session
                from services.api_client import connect_db
                from utils.db_context import load_database_context
                saved = load_active_session(_username)
                if saved and saved.get("host") and saved.get("database"):
                    res = connect_db(
                        host=saved["host"],
                        port=str(saved.get("port", 5432)),
                        username=saved.get("username", ""),
                        password=saved.get("password", ""),
                        database=saved["database"],
                        database_type=saved.get("database_type", "postgresql"),
                    )
                    if res.get("success"):
                        st.session_state["connected"] = True
                        st.session_state["db_info"] = saved
                        load_database_context(saved)
            except Exception:
                pass

# ---------------- THEME LOADER ---------------- #


def load_css():
    """Inject global premium CSS + Google Fonts for the entire application."""

    sidebar_css = ""
    sidebar_pref = st.session_state.get("pref_sidebar", "Expanded").lower()
    if sidebar_pref == "collapsed":
        sidebar_css = """
        section[data-testid="stSidebar"] { display: none !important; }
        """

    custom_css = """
    <!-- Google Fonts: Inter for UI, JetBrains Mono for code -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">

    <style>
    /* ───────────── ROOT ───────────── */
    *, *::before, *::after { box-sizing: border-box; }

    html, body, .stApp {
        overflow-x: hidden !important;
    }

    .stApp {
        background-color: #080E1A;
        color: #F1F5F9;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
    }

    /* ───────────── LAYOUT ───────────── */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem;
        padding-left: 1.75rem;
        padding-right: 1.75rem;
        max-width: 100% !important;
    }

    /* ───────────── SIDEBAR ───────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0E1624 0%, #0B1120 100%);
        border-right: 1px solid rgba(31,41,55,0.8);
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
        padding-top: 0.5rem !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0rem !important;
    }

    /* ───────────── TYPOGRAPHY ───────────── */
    h1 { font-size: 2rem; font-weight: 800; color: #F1F5F9; letter-spacing: -0.5px; }
    h2 { font-size: 1.4rem; font-weight: 700; color: #E2E8F0; }
    h3 { font-size: 1.1rem; font-weight: 600; color: #CBD5E1; }
    p  { color: #94A3B8; line-height: 1.65; }
    code { font-family: 'JetBrains Mono', monospace !important; }

    /* ───────────── GLOBAL BUTTONS ───────────── */
    .stButton > button,
    .stFormSubmitButton > button,
    button[data-testid^="baseButton-"] {
        background: rgba(30,41,59,0.7) !important;
        color: #E2E8F0 !important;
        border: 1px solid rgba(51,65,85,0.6) !important;
        border-radius: 8px !important;
        padding: 0.45rem 0.8rem !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
        font-family: 'Inter', sans-serif !important;
        width: 100% !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: none !important;
        cursor: pointer !important;
    }
    .stButton > button:hover,
    .stFormSubmitButton > button:hover,
    button[data-testid^="baseButton-"]:hover {
        background: rgba(99,102,241,0.15) !important;
        color: #FFFFFF !important;
        border-color: rgba(99,102,241,0.45) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 15px rgba(99,102,241,0.25) !important;
    }
    .stButton > button:active,
    .stFormSubmitButton > button:active,
    button[data-testid^="baseButton-"]:active {
        transform: translateY(0px) !important;
        background: rgba(99,102,241,0.25) !important;
    }

    /* Primary button */
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"],
    button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #6366F1, #8B5CF6) !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(99,102,241,0.35) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(99,102,241,0.55) !important;
        background: linear-gradient(135deg, #4F46E5, #7C3AED) !important;
    }
    .stButton > button p,
    .stFormSubmitButton > button p,
    button[data-testid^="baseButton-"] p {
        color: inherit !important;
    }

    /* ───────────── PASSWORD POPUP DIALOG CONNECT BUTTON OVERRIDE ───────────── */
    /* Target ONLY the Connect button (the 3rd button inside the dialog stModal overlay to bypass top-right close X) */
    div[data-testid="stModal"] button[data-testid^="baseButton-primary"],
    div[data-testid="stModal"] button[data-testid*="primary"],
    [data-testid="stModal"] button:nth-of-type(3),
    div[data-testid="stModal"] button:nth-of-type(3),
    [role="dialog"] button:nth-of-type(3),
    div[role="dialog"] button:nth-of-type(3) {
        background: linear-gradient(135deg, #8B5CF6, #7C3AED) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 12px !important;
        height: 46px !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(139,92,246,0.3) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    div[data-testid="stModal"] button[data-testid^="baseButton-primary"]:hover,
    div[data-testid="stModal"] button[data-testid*="primary"]:hover,
    [data-testid="stModal"] button:nth-of-type(3):hover,
    div[data-testid="stModal"] button:nth-of-type(3):hover,
    [role="dialog"] button:nth-of-type(3):hover,
    div[role="dialog"] button:nth-of-type(3):hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 22px rgba(139,92,246,0.5) !important;
        background: linear-gradient(135deg, #9333EA, #8B5CF6) !important;
        color: #FFFFFF !important;
    }

    /* ───────────── SIDEBAR BUTTONS ───────────── */
    section[data-testid="stSidebar"] .stButton > button {
        background: transparent;
        color: #94A3B8;
        border: 1px solid transparent;
        border-radius: 7px;
        font-weight: 500;
        text-align: left;
        justify-content: flex-start;
        height: 2.2rem !important;
        min-height: 2.2rem !important;
        max-height: 2.2rem !important;
        padding: 0 0.6rem !important;
        overflow: hidden;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(99,102,241,0.1);
        color: #E2E8F0;
        border-color: rgba(99,102,241,0.2);
        transform: translateX(3px);
        box-shadow: none;
    }
    section[data-testid="stSidebar"] .stButton > button p {
        text-align: left; 
        margin: 0;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        line-height: 2.2rem;
        color: inherit !important;
    }
    /* Ensure each button element has spacing so they never overlap */
    section[data-testid="stSidebar"] div.element-container:has(.stButton) {
        margin-bottom: 2px !important;
    }

    /* ───────────── INPUTS ───────────── */
    .stTextInput input,
    .stTextArea textarea {
        background-color: rgba(30,41,59,0.8) !important;
        color: #E2E8F0 !important;
        border-radius: 10px !important;
        border: 1px solid rgba(51,65,85,0.7) !important;
        padding: 10px 14px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.9rem !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }
    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: rgba(99,102,241,0.5) !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important;
        outline: none !important;
    }

    /* ───────────── SELECTBOX ───────────── */
    .stSelectbox div[data-baseweb="select"] {
        background-color: rgba(30,41,59,0.8) !important;
        border-radius: 10px !important;
    }
    .stSelectbox div[data-baseweb="select"] > div {
        color: #E2E8F0 !important;
    }

    /* ───────────── DATAFRAME ───────────── */
    .stDataFrame {
        border-radius: 12px !important;
        overflow: hidden !important;
        border: 1px solid rgba(51,65,85,0.5) !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.2) !important;
    }
    .stDataFrame th {
        background: rgba(99,102,241,0.1) !important;
        color: #A78BFA !important;
        font-weight: 700 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stDataFrame td { color: #CBD5E1 !important; font-size: 0.85rem !important; }

    /* ───────────── ALERTS ───────────── */
    .stAlert { border-radius: 10px !important; }
    .stSuccess { background: rgba(16,185,129,0.1) !important; border-color: rgba(16,185,129,0.3) !important; }
    .stError   { background: rgba(239,68,68,0.1) !important;  border-color: rgba(239,68,68,0.3) !important; }
    .stWarning { background: rgba(245,158,11,0.1) !important; border-color: rgba(245,158,11,0.3) !important; }
    .stInfo    { background: rgba(99,102,241,0.1) !important; border-color: rgba(99,102,241,0.3) !important; }

    /* ───────────── CODE BLOCKS ───────────── */
    .stCode, pre {
        background: rgba(10,14,28,0.95) !important;
        border: 1px solid rgba(99,102,241,0.2) !important;
        border-radius: 10px !important;
    }

    /* ───────────── METRICS ───────────── */
    [data-testid="metric-container"] {
        background: rgba(15,23,42,0.9);
        border: 1px solid rgba(51,65,85,0.5);
        padding: 16px 20px;
        border-radius: 14px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }

    /* ───────────── GLOBAL SCROLLBAR ───────────── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: rgba(15,23,42,0.4); border-radius: 3px; }
    ::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.3); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(99,102,241,0.5); }

    /* ───────────── SPINNER ───────────── */
    .stSpinner > div { border-top-color: #6366F1 !important; }

    /* ───────────── TABS ───────────── */
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 8px;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.5rem 1rem;
        background: transparent;
        border: none;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"] p {
        color: #94A3B8 !important;
        font-weight: 600;
        font-size: 0.95rem;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"]:hover p {
        color: #E2E8F0 !important;
    }
    div[data-testid="stTabs"] [aria-selected="true"] p {
        color: #FFFFFF !important;
    }
    div[data-testid="stTabs"] [aria-selected="true"] {
        /* User wants default red tab-highlight line, removing blue line */
    }

    /* ───────────── PLOTLY CHARTS ───────────── */
    .js-plotly-plot .plotly { border-radius: 10px; }

    /* ───────────── EXPANDER ───────────── */
    [data-testid="stExpander"] {
        background: rgba(15,23,42,0.6);
        border: 1px solid rgba(51,65,85,0.4);
        border-radius: 10px;
    }

    /* ───────────── FILE UPLOADER ───────────── */
    [data-testid="stFileUploader"] {
        background: rgba(15,23,42,0.6);
        border: 2px dashed rgba(99,102,241,0.25);
        border-radius: 12px;
        padding: 8px;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: rgba(99,102,241,0.45);
    }

    /* ───────────── PREMIUM ACTIVE TOGGLES ───────────── */
    div[data-testid="stToggle"] button[role="switch"][aria-checked="true"],
    div[data-testid="stToggle"] [data-checked="true"],
    button[role="switch"][aria-checked="true"] {
        background-color: #6366F1 !important;
    }
    div[data-testid="stToggle"] button[role="switch"] div[data-checked="true"] {
        background-color: #6366F1 !important;
    }

    /* ───────────── HIDE DEFAULT STREAMLIT CHROME ───────────── */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    [data-testid="stDecoration"] { display: none; }

    /* ═══════════════════════════════════════════════════════════════════════
       RESPONSIVE DESIGN — Mobile-first media queries
       ═══════════════════════════════════════════════════════════════════════ */

    /* ── LARGE TABLET / SMALL LAPTOP (≤ 1024px) ── */
    @media (max-width: 1024px) {
        .block-container {
            padding-left: 1.25rem !important;
            padding-right: 1.25rem !important;
        }
    }

    /* ── TABLET (≤ 768px) ── */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 0.5rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
        }

        /* Force ALL st.columns() to stack vertically on mobile, except inside the sidebar */
        section:not([data-testid="stSidebar"]) [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        section:not([data-testid="stSidebar"]) [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            flex: 1 1 100% !important;
            max-width: 100% !important;
            min-width: 100% !important;
            width: 100% !important;
        }

        /* Responsive typography */
        h1 { font-size: 1.4rem !important; letter-spacing: -0.3px !important; }
        h2 { font-size: 1.15rem !important; }
        h3 { font-size: 0.95rem !important; }

        /* Reduce button padding for mobile */
        .stButton > button,
        .stFormSubmitButton > button,
        button[data-testid^="baseButton-"] {
            padding: 0.5rem 0.6rem !important;
            font-size: 0.84rem !important;
            min-height: 42px !important;
        }

        /* Input fields: slightly larger touch targets */
        .stTextInput input,
        .stTextArea textarea {
            padding: 12px 12px !important;
            font-size: 0.88rem !important;
        }

        /* Selectbox: touch-friendly */
        .stSelectbox div[data-baseweb="select"] > div {
            min-height: 42px !important;
        }

        /* Tabs: scroll horizontally instead of wrapping on mobile */
        div[data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 4px !important;
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
            scrollbar-width: none !important;
            flex-wrap: nowrap !important;
        }
        div[data-testid="stTabs"] [data-baseweb="tab-list"]::-webkit-scrollbar {
            display: none !important;
        }
        div[data-testid="stTabs"] [data-baseweb="tab"] {
            padding: 6px 12px !important;
            font-size: 0.82rem !important;
            white-space: nowrap !important;
            flex-shrink: 0 !important;
        }

        /* Metrics container: tighter on mobile */
        [data-testid="metric-container"] {
            padding: 10px 14px !important;
        }

        /* Modal/dialog: full width on mobile */
        div[data-testid="stModal"] > div,
        div[role="dialog"] {
            width: 95vw !important;
            max-width: 95vw !important;
            margin: 0 auto !important;
            padding: 16px !important;
        }

        /* Code blocks: scroll horizontally */
        .stCode, pre {
            max-width: 100% !important;
            overflow-x: auto !important;
        }

        /* DataFrames: ensure horizontal scroll */
        .stDataFrame {
            max-width: 100% !important;
        }
        .stDataFrame > div {
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
        }
    }

    /* ── SMALL MOBILE (≤ 480px) ── */
    @media (max-width: 480px) {
        .block-container {
            padding-left: 0.4rem !important;
            padding-right: 0.4rem !important;
        }

        h1 { font-size: 1.2rem !important; }
        h2 { font-size: 0.98rem !important; }
        h3 { font-size: 0.85rem !important; }
        p { font-size: 0.78rem !important; }
        code { font-size: 0.78rem !important; }

        .stButton > button,
        .stFormSubmitButton > button,
        button[data-testid^="baseButton-"] {
            min-height: 36px !important;
            padding: 0.35rem 0.5rem !important;
            font-size: 0.78rem !important;
        }

        .stTextInput input,
        .stTextArea textarea {
            padding: 8px 10px !important;
            font-size: 0.8rem !important;
        }

        .stSelectbox div[data-baseweb="select"] > div {
            min-height: 34px !important;
        }

        [data-testid="metric-container"] {
            padding: 6px 10px !important;
        }

        div[data-testid="stModal"] > div,
        div[role="dialog"] {
            padding: 10px !important;
        }
    }

    /* ── EXTRA SMALL MOBILE (≤ 375px) ── */
    @media (max-width: 375px) {
        h1 { font-size: 1.1rem !important; }
        h2 { font-size: 0.92rem !important; }
        h3 { font-size: 0.8rem !important; }

        .stButton > button,
        .stFormSubmitButton > button,
        button[data-testid^="baseButton-"] {
            min-height: 34px !important;
            font-size: 0.74rem !important;
        }

        .stTextInput input,
        .stTextArea textarea {
            padding: 6px 8px !important;
            font-size: 0.76rem !important;
        }
    }

    /* ── TOUCH DEVICE — remove hover transforms that cause jank ── */
    @media (hover: none) and (pointer: coarse) {
        .stButton > button:hover,
        .stFormSubmitButton > button:hover,
        button[data-testid^="baseButton-"]:hover {
            transform: none !important;
        }
        .stButton > button[kind="primary"]:hover,
        .stFormSubmitButton > button[kind="primary"]:hover,
        button[data-testid="baseButton-primary"]:hover {
            transform: none !important;
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            transform: none !important;
        }
    }

    /* ── SIDEBAR MOBILE ADAPTATION ── */
    @media (max-width: 768px) {
        section[data-testid="stSidebar"],
        section[data-testid="stSidebar"] > div:first-child {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            z-index: 999999 !important;
            width: 80vw !important;
            max-width: 280px !important;
            min-width: unset !important;
            height: 100vh !important;
            background: linear-gradient(180deg, #0E1624 0%, #0B1120 100%) !important;
            border-right: 1px solid rgba(31,41,55,0.8) !important;
        }
        section[data-testid="stSidebar"] > div:first-child {
            overflow: hidden !important;
            position: relative !important;
        }
    }

    </style>
    """

    final_css = custom_css + f"\n<style>\n{sidebar_css}\n</style>"
    final_css_cleaned = "\n".join(line.lstrip() for line in final_css.split("\n"))
    st.markdown(final_css_cleaned, unsafe_allow_html=True)


load_css()

# ---------------- LOGIN CHECK ---------------- #

# Show login or signup only if not authenticated
if not st.session_state.get("authenticated", False):
    menu = st.session_state.get("menu", "Dashboard")
    if menu == "Signup":
        from pages.signup import show_signup
        show_signup()
    else:
        show_login()
    st.stop()


# ---------------- MENU ROUTING ---------------- #

menu = st.session_state.get(
    "menu",
    "Dashboard"
)
if menu == "Dashboard":

    show_dashboard()

elif menu == "Query History":

    show_query_history()

elif menu == "Recent Connections":
    from pages.past_connections import show_past_connections
    show_past_connections()

elif menu == "Settings":

    show_settings()

elif menu == "Profile":
    from pages.profile import show_profile
    show_profile()

else:

    show_dashboard()
import streamlit as st

from components.sidebar import render_sidebar
from utils.icons import get_icon
from utils.settings_manager import get_setting, sync_widget


def show_settings():
    render_sidebar()

    st.markdown("""
    <style>
    /* ── Page header ─────────────────────────────────────────────── */
    .sp-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #F1F5F9;
        margin: 6px 0 2px 0;
        letter-spacing: -0.01em;
    }
    .sp-subtitle {
        font-size: 0.82rem;
        color: #475569;
        margin-bottom: 28px;
    }

    /* ── Section heading (no box, just label + rule) ─────────────── */
    .sp-section-heading {
        font-size: 0.7rem;
        font-weight: 700;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin: 28px 0 14px 0;
    }

    /* ── DB cards ────────────────────────────────────────────────── */
    .info-card {
        background: rgba(30,41,59,0.6);
        border: 1px solid #1E293B;
        border-radius: 10px;
        padding: 14px 18px;
        min-height: 68px;
        margin-bottom: 2px;
    }
    .info-card-label {
        font-size: 0.67rem;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        font-weight: 600;
        margin-bottom: 5px;
    }
    .info-card-value {
        font-size: 0.92rem;
        font-weight: 600;
        color: #CBD5E1;
    }

    /* ── History stat cards ───────────────────────────────────────── */
    .hs-card {
        background: rgba(30,41,59,0.5);
        border: 1px solid #1E293B;
        border-radius: 10px;
        padding: 14px 16px;
        text-align: center;
    }
    .hs-val { font-size: 1.4rem; font-weight: 800; color: #E2E8F0; }
    .hs-lbl { font-size: 0.65rem; color: #475569; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.6px; }

    /* ── App info pills ───────────────────────────────────────────── */
    .app-strip {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 2px;
    }
    .app-pill {
        background: rgba(99,102,241,0.07);
        border: 1px solid rgba(99,102,241,0.15);
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 0.75rem;
        color: #64748B;
    }
    .app-pill span { font-weight: 700; color: #818CF8; margin-left: 4px; }

    /* ── Dividers ─────────────────────────────────────────────────── */
    .sp-rule { border: none; border-top: 1px solid #1E293B; margin: 0; }

    /* ── Logout row ───────────────────────────────────────────────── */
    .logout-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 0 4px 0;
    }
    .logout-row-left { font-size: 0.875rem; font-weight: 500; color: #94A3B8; }
    .logout-row-desc { font-size: 0.75rem; color: #334155; margin-top: 2px; }

    /* ── DB status card ──────────────────────────────────────────── */
    .db-status-card {
        background: rgba(30,41,59,0.4);
        border: 1px solid #1E293B;
        border-radius: 8px;
        padding: 14px 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 16px;
    }
    .db-status-block {
        display: flex;
        flex-direction: column;
    }
    .db-status-label {
        font-size: 0.65rem;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .db-status-val {
        font-size: 0.85rem;
        color: #CBD5E1;
        font-weight: 500;
    }

    /* ── Responsive Settings ── */
    @media (max-width: 768px) {
        div[data-testid="stAppViewBlockContainer"],
        div.block-container {
            padding-left: 14px !important;
            padding-right: 14px !important;
        }

        .sp-title { font-size: 1.25rem !important; margin-top: 4px !important; }
        .sp-subtitle { font-size: 0.78rem !important; margin-bottom: 12px !important; }
        .sp-section-heading { margin: 16px 0 8px 0 !important; font-size: 0.68rem !important; }
        .sp-rule { margin: 8px 0 !important; }
        .info-card { padding: 10px 12px !important; min-height: 56px !important; }
        
        /* DB Connection card mobile compact */
        .db-status-card {
            padding: 10px 14px !important;
            gap: 10px 12px !important;
        }
        .db-status-label {
            font-size: 0.58rem !important;
            margin-bottom: 2px !important;
        }
        .db-status-val {
            font-size: 0.78rem !important;
        }

        /* Stats Cards vertical stack */
        div[data-testid="stHorizontalBlock"]:has(.hs-card) {
            display: flex !important;
            flex-direction: column !important;
            gap: 8px !important;
            width: 100% !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.hs-card) > div[data-testid="stColumn"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            max-width: 100% !important;
        }
        .hs-card { padding: 10px 8px !important; }
        .hs-val { font-size: 1.15rem !important; }
        .hs-lbl { font-size: 0.58rem !important; margin-top: 1px !important; }
        
        /* Selectbox and dropdown sizing */
        div[data-testid="stHorizontalBlock"]:has(div[data-baseweb="select"]) {
            gap: 8px !important;
        }
        div[data-baseweb="select"] *,
        div[data-testid="stWidgetLabel"] p,
        div[data-testid="stRadio"] label p,
        div[data-testid="stRadio"] div[role="radiogroup"] * {
            font-size: 0.8rem !important;
        }

        /* Sign Out and Clear buttons heights */
        button[data-testid*="clear_history_btn"],
        button[data-testid*="logout_btn"] {
            height: 34px !important;
            line-height: 34px !important;
            font-size: 0.8rem !important;
        }
        button[data-testid*="clear_history_btn"] p,
        button[data-testid*="logout_btn"] p {
            font-size: 0.8rem !important;
        }
        
        .app-strip { gap: 6px !important; }
        .app-pill { font-size: 0.65rem !important; padding: 2px 8px !important; }
    }
    @media (max-width: 480px) {
        div[data-testid="stAppViewBlockContainer"],
        div.block-container {
            padding-left: 10px !important;
            padding-right: 10px !important;
        }

        .sp-title { font-size: 1.1rem !important; }
        .sp-subtitle { font-size: 0.72rem !important; margin-bottom: 8px !important; }
        .sp-section-heading { margin: 12px 0 6px 0 !important; font-size: 0.65rem !important; }
        .info-card { padding: 6px 8px !important; min-height: 44px !important; }
        
        .db-status-card {
            padding: 8px 10px !important;
            gap: 8px 8px !important;
        }
        .db-status-label {
            font-size: 0.55rem !important;
        }
        .db-status-val {
            font-size: 0.72rem !important;
        }

        .hs-card { padding: 8px 4px !important; }
        .hs-val { font-size: 0.95rem !important; }
        .hs-lbl { font-size: 0.52rem !important; }
        
        div[data-baseweb="select"] *,
        div[data-testid="stWidgetLabel"] p,
        div[data-testid="stRadio"] label p,
        div[data-testid="stRadio"] div[role="radiogroup"] * {
            font-size: 0.75rem !important;
        }

        button[data-testid*="clear_history_btn"],
        button[data-testid*="logout_btn"] {
            height: 30px !important;
            line-height: 30px !important;
            font-size: 0.75rem !important;
        }
        button[data-testid*="clear_history_btn"] p,
        button[data-testid*="logout_btn"] p {
            font-size: 0.75rem !important;
        }

        .app-strip { gap: 4px !important; }
        .app-pill { font-size: 0.58rem !important; padding: 1px 6px !important; }
    }
    </style>
    """, unsafe_allow_html=True)

    # ─── Page header ─────────────────────────────────────────────── #
    st.markdown("""
    <div class='sp-title'>Settings</div>
    <div class='sp-subtitle'>Manage your connection, AI, and preferences</div>
    <hr class='sp-rule'>
    """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════ #
    # 1. CURRENT DATABASE CONNECTION
    # ═══════════════════════════════════════════════════════════════ #
    st.markdown("<div class='sp-section-heading'>Database Connection</div>", unsafe_allow_html=True)

    if st.session_state.get("connected"):
        db_info     = st.session_state.get("db_info", {})
        db_type     = db_info.get("database_type", db_info.get("db_type", "N/A")).upper()
        db_icon_name = "mysql" if "MYSQL" in db_type else ("postgres" if "POSTGRES" in db_type else "database")
        db_icon_svg  = get_icon(db_icon_name, size=13, color="#A78BFA")

        st.markdown(f"""
        <div class="db-status-card">
            <div class="db-status-block">
                <span class="db-status-label">Status</span>
                <span class="db-status-val" style="color: #10B981; font-weight: 600;">● Connected</span>
            </div>
            <div class="db-status-block">
                <span class="db-status-label">Type</span>
                <span class="db-status-val">{db_icon_svg}&nbsp;{db_type}</span>
            </div>
            <div class="db-status-block">
                <span class="db-status-label">Database</span>
                <span class="db-status-val">{db_info.get('database', 'N/A')}</span>
            </div>
            <div class="db-status-block">
                <span class="db-status-label">Host</span>
                <span class="db-status-val">{db_info.get('host', 'N/A')}:{db_info.get('port', 'N/A')}</span>
            </div>
            <div class="db-status-block">
                <span class="db-status-label">User</span>
                <span class="db-status-val">{db_info.get('username', 'N/A')}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("No database connected. Go to Dashboard to connect.")

    # ═══════════════════════════════════════════════════════════════ #
    # 2. AI PREFERENCES
    # ═══════════════════════════════════════════════════════════════ #
    st.markdown("<hr class='sp-rule' style='margin-top:20px;'><div class='sp-section-heading'>AI Preferences</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="medium")
    with col1:
        opts4 = ["Detailed", "Short", "None"]
        idx4  = opts4.index(get_setting("explanation_mode")) if get_setting("explanation_mode") in opts4 else 0
        st.selectbox("Query Explanation Mode", opts4, index=idx4, key="ai_explain",
                     on_change=sync_widget, args=("explanation_mode", "ai_explain"))

    with col2:
        opts5 = ["Auto (AI Recommended)", "Bar Chart", "Line Chart", "Pie Chart", "Scatter Plot"]
        idx5  = opts5.index(get_setting("chart_preference")) if get_setting("chart_preference") in opts5 else 0
        st.selectbox("Chart Preference", opts5, index=idx5, key="ai_chart",
                     on_change=sync_widget, args=("chart_preference", "ai_chart"))

    # ═══════════════════════════════════════════════════════════════ #
    # 3. QUERY LIMITS
    # ═══════════════════════════════════════════════════════════════ #
    st.markdown("<hr class='sp-rule' style='margin-top:6px;'><div class='sp-section-heading'>Query Limits</div>", unsafe_allow_html=True)

    col_lim, col_sp = st.columns([2, 3], gap="medium")
    with col_lim:
        limit_opts = ["Auto", "Limited"]
        idx6 = limit_opts.index(get_setting("row_limit_mode")) if get_setting("row_limit_mode") in limit_opts else 0
        limit_mode = st.radio(
            "Row Limit Mode", limit_opts, index=idx6, horizontal=True,
            help="Auto = AI chooses, Limited = fixed cap",
            key="db_row_limit_mode",
            on_change=sync_widget, args=("row_limit_mode", "db_row_limit_mode"),
        )
        if limit_mode == "Limited":
            st.number_input(
                "Custom Row Limit", min_value=1, max_value=100000,
                value=get_setting("row_limit"), step=10,
                key="db_row_limit",
                on_change=sync_widget, args=("row_limit", "db_row_limit"),
            )

    # ═══════════════════════════════════════════════════════════════ #
    # 4. QUERY HISTORY
    # ═══════════════════════════════════════════════════════════════ #
    st.markdown("<hr class='sp-rule' style='margin-top:6px;'><div class='sp-section-heading'>Query History</div>", unsafe_allow_html=True)

    if not st.session_state.get("connected"):
        history = []
    else:
        db_info = st.session_state.get("db_info", {})
        current_db = db_info.get("database", "")
        history = [
            item for item in st.session_state.get("query_history", [])
            if item.get("database_name") == current_db
        ]
    total_q = len(history)

    h1, h2, h3 = st.columns(3, gap="small")
    for col, val, label in [(h1, str(total_q), "Total Queries"), (h2, "0", "Queries Today"), (h3, "0.8s", "Avg Runtime")]:
        with col:
            st.markdown(f"""
            <div class='hs-card'>
                <div class='hs-val'>{val}</div>
                <div class='hs-lbl'>{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    def _clear_history():
        st.session_state["query_history"] = []
        from services.history_client import clear_query_history
        clear_query_history()

    col_clr, col_sp2 = st.columns([1, 5])
    with col_clr:
        st.button("Clear History", key="clear_history_btn", on_click=_clear_history, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════ #
    # 5. APPLICATION INFO
    # ═══════════════════════════════════════════════════════════════ #
    st.markdown("<hr class='sp-rule' style='margin-top:6px;'><div class='sp-section-heading'>About</div>", unsafe_allow_html=True)

    st.markdown("""
    <div class='app-strip'>
        <div class='app-pill'>AI Engine <span>Agentic AI V1</span></div>
        <div class='app-pill'>Runtime <span>Python + FastAPI</span></div>
        <div class='app-pill'>Database Support <span>MySQL &middot; PostgreSQL</span></div>
        <div class='app-pill'>Status <span>Active</span></div>
    </div>
    """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════ #
    # 6. ACCOUNT ACTIONS
    # ═══════════════════════════════════════════════════════════════ #
    st.markdown("<hr class='sp-rule' style='margin-top:20px;'><div class='sp-section-heading'>Account</div>", unsafe_allow_html=True)

    col_logout, col_sp4 = st.columns([1, 5])
    with col_logout:
        if st.button("Sign out", key="logout_btn", use_container_width=True):
            try:
                from utils.settings_manager import log_activity
                log_activity("Logged out of account")
            except Exception:
                pass

            keys_to_reset = {
                "authenticated": False,
                "access_token": None,
                "user_profile": {},
                "remember_me": False,
                "menu": "Dashboard",
                "connected": False,
                "db_info": {},
                "schema_data": None,
                "schema_raw": {},
                "schema_loaded": False,
                "schema_load_error": None,
                "db_stats": {},
                "query_suggestions": [],
                "query_history": [],
                "query_result": None,
                "generated_sql": "",
                "current_query": "",
                "last_result": None,
                "_settings_loaded": False,
                "_history_loaded": False,
                "_connection_restored": False,
                "_token_refreshed": False,
                "_fresh_login": False,
            }
            for key, val in keys_to_reset.items():
                st.session_state[key] = val
            st.query_params.clear()
            st.rerun()

    st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)

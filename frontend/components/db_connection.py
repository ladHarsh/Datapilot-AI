import streamlit as st

from services.api_client import connect_db
from utils.db_context import load_database_context
from utils.icons import get_icon


def render_db_connection():

    st.markdown("""
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.db-form-card-marker) {
        background: linear-gradient(135deg, rgba(15,23,42,0.95), rgba(30,41,59,0.8)) !important;
        border: 1px solid rgba(99,102,241,0.25) !important;
        border-radius: 16px !important;
        padding: 28px 28px 24px 28px !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.03) !important;
        margin-top: 8px !important;
    }
    /* Reset outer container if nested to prevent card-inside-card bug */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div[data-testid="stVerticalBlockBorderWrapper"] .db-form-card-marker) {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }
    .db-form-header-row {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 4px;
    }
    .db-form-icon-pill {
        color: #8B5CF6;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .db-form-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #E2E8F0;
    }
    .db-form-caption {
        font-size: 0.82rem;
        color: #64748B;
        margin-bottom: 20px;
        padding-left: 0px;
    }
    .desktop-desc { display: inline; }
    .mobile-desc { display: none; }

    /* ── Responsive DB Connection Form ── */
    @media (max-width: 768px) {
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.db-form-card-marker) {
            padding: 20px 16px 16px 16px !important;
            border-radius: 12px !important;
        }
        .db-form-title { font-size: 0.95rem !important; }
        .db-form-caption { font-size: 0.76rem !important; margin-bottom: 14px !important; }
        .desktop-desc { display: none !important; }
        .mobile-desc { display: inline !important; }
    }
    @media (max-width: 480px) {
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.db-form-card-marker) {
            padding: 16px 12px 12px 12px !important;
            border-radius: 10px !important;
        }
        .db-form-title { font-size: 0.85rem !important; }
        .db-form-caption { font-size: 0.7rem !important; margin-bottom: 8px !important; }
    }
    </style>

    <script>
    // Periodically search for inputs and disable browser autofill/autocomplete recommendations
    const disableCredentialsAutofill = () => {
        const inputs = document.querySelectorAll('input');
        inputs.forEach(input => {
            input.setAttribute('autocomplete', 'new-password');
            input.setAttribute('autocorrect', 'off');
            input.setAttribute('spellcheck', 'false');
        });
    };
    
    // Run immediately and set intervals to handle dynamic Streamlit re-renders
    disableCredentialsAutofill();
    const autofillInterval = setInterval(disableCredentialsAutofill, 500);
    
    // Clear interval after 5 seconds to prevent unnecessary processing
    setTimeout(() => {
        clearInterval(autofillInterval);
    }, 5000);
    </script>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("<div class='db-form-card-marker'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div class='db-form-header-row'>
            <div class='db-form-title'>Initialize Database Connection</div>
        </div>
        <div class='db-form-caption'>
            <span class='desktop-desc'>Enterprise-grade connectivity — MySQL &amp; PostgreSQL supported with encrypted sessions</span>
            <span class='mobile-desc'>Connect MySQL or PostgreSQL databases with secure sessions</span>
        </div>
        """, unsafe_allow_html=True)

        # Database Type selector
        db_type = st.selectbox(
            "Database Type",
            ["MySQL", "PostgreSQL"],
            format_func=lambda x: f"MySQL Database" if x == "MySQL" else f"PostgreSQL Database"
        )

        default_port = "3306" if db_type == "MySQL" else "5432"

        # Host & Port row
        col_host, col_port = st.columns([3, 1])
        with col_host:
            host = st.text_input(
                "Host",
                value="",
                placeholder="localhost or IP address"
            )
        with col_port:
            port = st.text_input(
                "Port",
                value="",
                placeholder=default_port
            )

        # Username & Password row
        col_user, col_pass = st.columns(2)
        with col_user:
            username = st.text_input(
                "Username",
                value="",
                placeholder="Database username"
            )
        with col_pass:
            password = st.text_input(
                "Password",
                value="",
                type="password",
                placeholder="Enter database password"
            )

        # Database Name row (takes full width)
        database = st.text_input(
            "Database Name",
            value="",
            placeholder="e.g. sales_db"
        )

        st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)

        if st.button("Initialize Database", type="primary", use_container_width=True):

            if not host or not username or not database or not port or not password:
                st.error("Please fill in all database connection details before connecting.")
            else:
                with st.spinner("Connecting to database..."):
                    result = connect_db(host, port, username, password, database, db_type)

                if result.get("success") or result.get("status") == "ok":
                    st.session_state["connected"] = True
                    db_info = {
                        "host": host,
                        "port": int(port),
                        "username": username,
                        "password": password,
                        "database": database,
                        "database_type": db_type.lower(),
                    }
                    st.session_state["db_info"] = db_info

                    with st.spinner("Loading schema and metrics..."):
                        ok, msg = load_database_context(db_info, force_refresh=True)

                    if ok:
                        # Automatically store successfully connected database (passwords are NOT saved to .connections.json)
                        try:
                            from utils.connection_manager import save_connection, save_active_session
                            save_connection(
                                host=host,
                                port=int(port),
                                username=username,
                                database=database,
                                database_type=db_type
                            )
                            # Also persist the full connection (with password) for refresh restore
                            _uname = st.session_state.get("user_profile", {}).get("username", "default")
                            save_active_session(_uname, db_info)
                        except Exception:
                            pass
                        
                        try:
                            from utils.settings_manager import log_activity
                            log_activity(f"Connected to database: '{database}' ({db_type.upper()})")
                        except Exception:
                            pass
                        st.success(f"Connected to {db_type} database successfully!")
                        st.rerun()
                    else:
                        st.session_state["connected"] = False
                        st.error(f"Connected but failed to load schema: {msg}")
                else:
                    error_msg = result.get("message", "Unknown error occurred during connection.")
                    st.error(f"Connection Failed: {error_msg}")
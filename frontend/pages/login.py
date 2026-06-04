import streamlit as st
import os
from utils.icons import get_icon

def show_login():

    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        st.markdown("""
        <style>
        [data-testid="column"]:nth-of-type(2) {
            background: linear-gradient(145deg, #1E293B, #0F172A);
            padding: 3rem 2rem;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(99,102,241,0.15);
            border: 1px solid rgba(99, 102, 241, 0.2);
            margin-top: 4rem;
        }
        .login-logo-pill {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-bottom: 0.25rem;
        }
        .login-logo-icon {
            background: linear-gradient(135deg, #6366F1, #8B5CF6);
            border-radius: 12px;
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 15px rgba(99,102,241,0.4);
            color: white;
        }
        .brand-title {
            font-size: 2.1rem;
            font-weight: 800;
            background: linear-gradient(135deg, #6366F1, #A78BFA);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: -0.5px;
        }
        .brand-tagline {
            text-align: center;
            color: #64748B;
            font-size: 0.85rem;
            letter-spacing: 0.5px;
            margin-bottom: 0.25rem;
        }
        .brand-subtitle {
            text-align: center;
            color: #94A3B8;
            font-size: 0.95rem;
            margin-bottom: 2rem;
        }

        /* ── Responsive Login ── */
        @media (max-width: 768px) {
            [data-testid="column"]:nth-of-type(1),
            [data-testid="column"]:nth-of-type(3) {
                display: none !important;
            }
            [data-testid="column"]:nth-of-type(2) {
                flex: 1 1 100% !important;
                max-width: 100% !important;
                min-width: 100% !important;
                padding: 1.5rem 1rem !important;
                margin-top: 1rem !important;
                border-radius: 16px !important;
            }
            .brand-title { font-size: 1.6rem !important; }
        }
        @media (max-width: 480px) {
            [data-testid="column"]:nth-of-type(2) {
                padding: 1rem 0.75rem !important;
                margin-top: 0.25rem !important;
                border-radius: 12px !important;
            }
            .login-logo-icon {
                width: 36px !important;
                height: 36px !important;
                border-radius: 10px !important;
            }
            .login-logo-icon svg {
                width: 18px !important;
                height: 18px !important;
            }
            .brand-title { font-size: 1.3rem !important; }
            .brand-tagline { font-size: 0.74rem !important; }
            .brand-subtitle { font-size: 0.8rem !important; margin-bottom: 1rem !important; }
        }
        </style>
        """, unsafe_allow_html=True)

        logo_icon_svg = get_icon("compass", size=24, color="white", stroke_width=2.0)

        st.markdown(f"""
        <div class='login-logo-pill'>
            <div class='login-logo-icon'>{logo_icon_svg}</div>
            <span class='brand-title'>DataPilot AI</span>
        </div>
        <p class='brand-tagline'>✦ AI-Powered Database Analytics Platform ✦</p>
        <p class='brand-subtitle'>Secure System Login</p>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Username or Email address",
                placeholder="Enter your username or email"
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password"
            )

            st.markdown("<br>", unsafe_allow_html=True)

            submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)

            if submitted:
                from services.auth_client import login_user
                res = login_user(username, password)

                # Fallback to hardcoded admin if DB doesn't have it (for development)
                if not res.get("success") and username == "admin" and password == "admin":
                    res = {"success": True, "user": {"username": "admin", "role": "admin"}}

                if res.get("success"):
                    st.session_state["authenticated"] = True
                    user_prof = res.get("user", {})
                    st.session_state["user_profile"] = user_prof

                    # Load user settings immediately on login and reset timeline for a fresh session
                    try:
                        from utils.settings_manager import load_settings_from_file, save_setting, log_activity
                        load_settings_from_file(user_prof.get("username", username))
                        st.session_state["_settings_loaded"] = True
                        save_setting("activity_timeline", [])  # Clear previous timeline history
                        log_activity(f"Logged in to account: {user_prof.get('username', username)}")
                    except Exception:
                        pass

                    # Clear any leftover DB state from a previous user on this tab
                    st.session_state["connected"] = False
                    st.session_state["db_info"] = {}
                    st.session_state["schema_data"] = None
                    st.session_state["schema_raw"] = {}
                    st.session_state["schema_loaded"] = False
                    st.session_state["db_stats"] = {}
                    st.session_state["query_suggestions"] = []
                    st.session_state["query_history"] = []
                    st.session_state["last_result"] = None

                    # Persist auth credentials for silent re-login on refresh
                    try:
                        from utils.connection_manager import save_auth_credentials
                        save_auth_credentials(user_prof.get("username", username), password)
                    except Exception:
                        pass

                    # Mark as fresh login so auto-restore doesn't connect old DB session
                    st.session_state["_fresh_login"] = True

                    # Persist login state across reloads
                    st.query_params["auth"] = "true"
                    st.query_params["user"] = user_prof.get("username", username)
                    st.query_params["role"] = user_prof.get("role", "admin")
                    st.query_params["page"] = "Dashboard"
                    if "access_token" in st.session_state:
                        st.query_params["token"] = st.session_state["access_token"]
                    
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")

        st.markdown("<div style='text-align: center; margin-top: 1rem; color: #64748B; font-size: 0.9rem;'>Don't have an account?</div>", unsafe_allow_html=True)
        if st.button("Create Account", use_container_width=True):
            st.session_state["menu"] = "Signup"
            st.rerun()
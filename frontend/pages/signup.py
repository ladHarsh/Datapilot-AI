import streamlit as st
from services.auth_client import signup_user
from utils.icons import get_icon

import time

def show_signup():
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
        .signup-logo-pill {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-bottom: 0.25rem;
        }
        .signup-logo-icon {
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
        .su-brand-title {
            font-size: 2.1rem;
            font-weight: 800;
            background: linear-gradient(135deg, #6366F1, #A78BFA);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: -0.5px;
        }
        .su-tagline {
            text-align: center;
            color: #64748B;
            font-size: 0.85rem;
            letter-spacing: 0.5px;
            margin-bottom: 0.25rem;
        }
        .su-heading {
            text-align: center;
            font-size: 1.4rem;
            font-weight: 700;
            color: #F8FAFC;
            margin-bottom: 0.2rem;
            margin-top: 1rem;
        }
        .su-subtitle {
            text-align: center;
            color: #94A3B8;
            font-size: 0.9rem;
            margin-bottom: 2rem;
        }

        /* ── Responsive Signup ── */
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
            .su-brand-title { font-size: 1.6rem !important; }
        }
        @media (max-width: 480px) {
            [data-testid="column"]:nth-of-type(2) {
                padding: 1rem 0.75rem !important;
                margin-top: 0.25rem !important;
                border-radius: 12px !important;
            }
            .signup-logo-icon {
                width: 36px !important;
                height: 36px !important;
                border-radius: 10px !important;
            }
            .signup-logo-icon svg {
                width: 18px !important;
                height: 18px !important;
            }
            .su-brand-title { font-size: 1.3rem !important; }
            .su-tagline { font-size: 0.74rem !important; }
            .su-heading { font-size: 1rem !important; }
            .su-subtitle { font-size: 0.76rem !important; margin-bottom: 1rem !important; }
        }
        </style>
        """, unsafe_allow_html=True)

        logo_icon_svg = get_icon("compass", size=24, color="white", stroke_width=2.0)

        st.markdown(f"""
        <div class='signup-logo-pill'>
            <div class='signup-logo-icon'>{logo_icon_svg}</div>
            <span class='su-brand-title'>DataPilot AI</span>
        </div>
        <p class='su-tagline'>✦ AI-Powered Database Analytics Platform ✦</p>
        <p class='su-heading'>Create Account</p>
        <p class='su-subtitle'>Start your AI analytics journey today</p>
        """, unsafe_allow_html=True)

        with st.form("signup_form", clear_on_submit=True):
            username = st.text_input("Username", placeholder="Choose a username")
            email = st.text_input("Email", placeholder="your@email.com")
            password = st.text_input("Password", type="password", placeholder="Min 8 characters")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Repeat password")

            st.markdown("<br>", unsafe_allow_html=True)
            submit = st.form_submit_button("Create Account", type="primary", use_container_width=True)

            if submit:
                if not username or not email or not password:
                    st.error("Please fill in all fields.")
                elif password != confirm_password:
                    st.error("Passwords do not match!")
                else:
                    success, msg = signup_user(username, email, password)
                    if success:
                        from services.auth_client import login_user
                        login_res = login_user(username, password)
                        if login_res.get("success"):
                            st.session_state["authenticated"] = True
                            st.session_state["user_profile"] = login_res.get("user", {"username": username, "email": email, "role": "user"})
                            st.session_state["menu"] = "Dashboard"
                            # Explicitly clear any DB state from previous user on same tab
                            st.session_state["connected"] = False
                            st.session_state["db_info"] = {}
                            st.session_state["schema_data"] = None
                            st.session_state["schema_raw"] = {}
                            st.session_state["schema_loaded"] = False
                            st.session_state["db_stats"] = {}
                            st.session_state["query_suggestions"] = []
                            st.session_state["query_history"] = []
                            st.session_state["last_result"] = None
                            # Save auth credentials for future refresh restores
                            try:
                                from utils.connection_manager import save_auth_credentials
                                save_auth_credentials(username, password)
                            except Exception:
                                pass
                            # Mark as fresh signup — do NOT auto-restore any old DB session
                            st.session_state["_fresh_login"] = True
                            st.rerun()
                        else:
                            st.error(f"Account created, but auto-login failed: {login_res.get('error')}. Please login manually.")
                    else:
                        st.error(msg)

        st.markdown("<div style='text-align: center; margin-top: 1rem; color: #64748B; font-size: 0.9rem;'>Already have an account?</div>", unsafe_allow_html=True)
        if st.button("Back to Login", use_container_width=True):
            st.session_state["menu"] = "Login"
            st.rerun()

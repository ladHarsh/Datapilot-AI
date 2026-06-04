import streamlit as st

from components.sidebar import render_sidebar
from services.profile_client import (
    fetch_user_profile,
    update_user_profile,
    change_password,
)
from utils.icons import get_icon


def _load_profile() -> dict:
    if not st.session_state.get("access_token"):
        return st.session_state.get("user_profile", {})

    result = fetch_user_profile()
    if result.get("success"):
        profile = result.get("data", {})
        st.session_state["user_profile"] = profile
        return profile
    return st.session_state.get("user_profile", {})


def show_profile():
    render_sidebar()

    st.markdown("""
    <style>
    .profile-page-css { padding-top: 0; }
    .profile-top-card {
        background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1));
        border: 1px solid rgba(99,102,241,0.25);
        border-radius: 18px;
        padding: 24px 28px;
        display: flex;
        align-items: center;
        gap: 20px;
        margin-top: 10px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .profile-avatar-big {
        background: linear-gradient(135deg, #6366F1, #8B5CF6);
        border-radius: 16px;
        width: 64px;
        height: 64px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        font-weight: 800;
        color: white;
        flex-shrink: 0;
        box-shadow: 0 6px 20px rgba(99,102,241,0.4);
    }
    .profile-top-header-row {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .profile-info-title {
        font-size: 1.35rem;
        font-weight: 800;
        color: #F8FAFC;
        line-height: 1.2;
    }
    .profile-info-sub {
        font-size: 0.82rem;
        color: #64748B;
        margin-top: 2px;
    }
    .profile-active-badge {
        background: rgba(16,185,129,0.15);
        border: 1px solid rgba(16,185,129,0.3);
        border-radius: 20px;
        padding: 3px 10px;
        font-size: 0.72rem;
        color: #10B981;
        font-weight: 600;
        margin-top: 6px;
        display: inline-block;
    }
    .profile-metric-card {
        background: linear-gradient(135deg, rgba(30,41,59,0.95), rgba(15,23,42,0.9));
        border: 1px solid rgba(99,102,241,0.15);
        border-radius: 14px;
        padding: 16px 18px;
        text-align: center;
        box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        position: relative;
        overflow: hidden;
    }
    .profile-metric-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, #6366F1, #8B5CF6);
        border-radius: 14px 14px 0 0;
    }
    .pmc-icon { display: flex; align-items: center; justify-content: center; margin-bottom: 6px; }
    .pmc-value { font-size: 1.5rem; font-weight: 800; color: #F8FAFC; }
    .pmc-label { font-size: 0.72rem; color: #64748B; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
    .section-header {
        font-size: 0.7rem;
        font-weight: 700;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin: 28px 0 14px 0;
    }
    .activity-item {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 10px 0;
        border-bottom: 1px solid rgba(30,41,59,0.8);
    }
    .activity-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: #6366F1;
        margin-top: 5px;
        flex-shrink: 0;
        box-shadow: 0 0 6px rgba(99,102,241,0.5);
    }
    .activity-text { font-size: 0.85rem; color: #94A3B8; }
    .activity-time { font-size: 0.72rem; color: #475569; }
    .security-card {
        background: rgba(16,185,129,0.08);
        border: 1px solid rgba(16,185,129,0.2);
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .security-icon-pill {
        color: #10B981;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .security-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #10B981;
    }
    .security-sub {
        font-size: 0.78rem;
        color: #64748B;
        margin-top: 2px;
    }
    .compact-btn-row { display: flex; gap: 8px; margin-top: 10px; }
    .tab-settings-area {
        background: rgba(15,23,42,0.6);
        border: 1px solid #1E293B;
        border-radius: 14px;
        padding: 20px;
        margin-top: 10px;
    }

    /* ── Responsive Profile ── */
    @media (max-width: 768px) {
        div[data-testid="stAppViewBlockContainer"],
        div.block-container {
            padding-left: 14px !important;
            padding-right: 14px !important;
        }

        .profile-top-card {
            display: flex !important;
            flex-direction: row !important;
            align-items: center !important;
            gap: 12px !important;
            padding: 12px 14px !important;
            margin-top: 6px !important;
            margin-bottom: 12px !important;
        }
        .profile-avatar-big {
            width: 40px !important;
            height: 40px !important;
            font-size: 18px !important;
            border-radius: 10px !important;
        }
        .profile-info-title { font-size: 1.05rem !important; }
        .profile-info-sub { font-size: 0.75rem !important; }
        .profile-active-badge { font-size: 0.65rem !important; padding: 2px 6px !important; margin-top: 4px !important; }
        
        /* Layout stats metrics as a 2x2 grid using flex wrap to prevent Streamlit float overlaps */
        div[data-testid="stHorizontalBlock"]:has(.profile-metric-card) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 8px !important;
            width: 100% !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.profile-metric-card) > div[data-testid="stColumn"] {
            flex: 1 1 calc(50% - 8px) !important;
            width: calc(50% - 8px) !important;
            max-width: calc(50% - 8px) !important;
            margin: 0 !important;
        }
        .profile-metric-card {
            padding: 10px 12px !important;
            border-radius: 10px !important;
        }
        .pmc-value { font-size: 1.15rem !important; }
        .pmc-label { font-size: 0.62rem !important; margin-top: 2px !important; }
        .section-header { margin: 16px 0 8px 0 !important; font-size: 0.68rem !important; }
        
        /* Density activity timeline */
        .activity-item {
            padding: 6px 0 !important;
            gap: 8px !important;
        }
        .activity-dot {
            width: 6px !important;
            height: 6px !important;
            margin-top: 4px !important;
        }
        .activity-text { font-size: 0.76rem !important; }
        .activity-time { font-size: 0.66rem !important; margin-top: 1px !important; }
        
        /* Form areas and side-by-side action buttons */
        .tab-settings-area {
            padding: 12px !important;
            border-radius: 10px !important;
            margin-top: 6px !important;
            max-width: 440px !important;
        }
        .tab-settings-area div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 8px !important;
            width: 100% !important;
        }
        .tab-settings-area div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            flex: 1 1 50% !important;
            width: 50% !important;
            max-width: 50% !important;
        }
        .tab-settings-area button {
            height: 34px !important;
            line-height: 34px !important;
            font-size: 0.8rem !important;
            border-radius: 8px !important;
        }
        .tab-settings-area button p,
        .tab-settings-area button span {
            font-size: 0.8rem !important;
        }
        .tab-settings-area div[data-testid="stWidgetLabel"] p {
            font-size: 0.78rem !important;
        }
        .tab-settings-area input {
            font-size: 0.78rem !important;
            height: 34px !important;
        }
        .compact-btn-row { flex-direction: column !important; gap: 6px !important; }
    }
    @media (max-width: 480px) {
        div[data-testid="stAppViewBlockContainer"],
        div.block-container {
            padding-left: 10px !important;
            padding-right: 10px !important;
        }

        .profile-top-card { padding: 8px 10px !important; gap: 8px !important; }
        .profile-avatar-big {
            width: 32px !important;
            height: 32px !important;
            font-size: 14px !important;
            border-radius: 8px !important;
        }
        .profile-info-title { font-size: 0.95rem !important; }
        .profile-info-sub { font-size: 0.7rem !important; }
        .profile-active-badge { font-size: 0.6rem !important; }
        .profile-metric-card { padding: 8px 6px !important; }
        .pmc-value { font-size: 1rem !important; }
        .pmc-label { font-size: 0.58rem !important; }
        .section-header { margin: 12px 0 6px 0 !important; font-size: 0.65rem !important; }
        .activity-item { padding: 4px 0 !important; }
        .activity-text { font-size: 0.72rem !important; }
        .activity-time { font-size: 0.62rem !important; }
        .tab-settings-area {
            padding: 8px !important;
            border-radius: 8px !important;
            max-width: 360px !important;
        }
        .tab-settings-area button {
            height: 30px !important;
            line-height: 30px !important;
            font-size: 0.75rem !important;
            border-radius: 6px !important;
        }
        .tab-settings-area button p,
        .tab-settings-area button span {
            font-size: 0.75rem !important;
        }
        .tab-settings-area div[data-testid="stWidgetLabel"] p {
            font-size: 0.72rem !important;
        }
        .tab-settings-area input {
            font-size: 0.72rem !important;
            height: 30px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    if not st.session_state.get("authenticated"):
        st.warning("Please log in to view your profile.")
        return

    if not st.session_state.get("access_token"):
        st.warning("Session token missing. Please log out and log in again.")
        return

    profile = _load_profile()
    username = profile.get("username", "—")
    email = profile.get("email", "—")
    role = str(profile.get("role", "user")).capitalize()
    full_name = profile.get("full_name") or username
    initials = username[0].upper() if username else "U"

    user_header_icon = get_icon("user", size=18, color="white")

    # ---- TOP PROFILE CARD ---- #
    st.markdown(f"""
    <div class='profile-top-card'>
        <div class='profile-avatar-big'>{initials}</div>
        <div>
            <div class='profile-top-header-row'>
                {user_header_icon}
                <div class='profile-info-title'>{full_name}</div>
            </div>
            <div class='profile-info-sub'>User Account &bull; {email}</div>
            <div class='profile-active-badge'>🟢 Active Session &bull; {role}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════ #
    # 1. ACCOUNT STATISTICS
    # ═══════════════════════════════════════════════════════════════ #
    st.markdown("<div class='section-header'>Account Statistics</div>", unsafe_allow_html=True)

    history = st.session_state.get("query_history", [])

    # 1. Total Queries
    total_queries = len(history)

    # 2. Queries Today
    import datetime
    today_str = datetime.date.today().isoformat()
    queries_today = sum(1 for item in history if today_str in str(item.get("timestamp", "")))

    # 3. Avg Runtime
    durations = [item.get("execution_duration", 0.0) for item in history if item.get("execution_duration") is not None]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    # 4. Unique Databases
    unique_dbs = len(set(item.get("database_name") for item in history if item.get("database_name")))

    col_m1, col_m2, col_m3, col_m4 = st.columns(4, gap="medium")
    with col_m1:
        st.markdown(f"""
        <div class='profile-metric-card'>
            <div class='pmc-icon'>{get_icon("terminal", size=20, color="#818CF8")}</div>
            <div class='pmc-value'>{total_queries}</div>
            <div class='pmc-label'>Total Queries</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""
        <div class='profile-metric-card'>
            <div class='pmc-icon'>{get_icon("activity", size=20, color="#818CF8")}</div>
            <div class='pmc-value'>{queries_today}</div>
            <div class='pmc-label'>Queries Today</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m3:
        st.markdown(f"""
        <div class='profile-metric-card'>
            <div class='pmc-icon'>{get_icon("clock", size=20, color="#818CF8")}</div>
            <div class='pmc-value'>{avg_duration:.2f}s</div>
            <div class='pmc-label'>Avg Runtime</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m4:
        st.markdown(f"""
        <div class='profile-metric-card'>
            <div class='pmc-icon'>{get_icon("database", size=20, color="#818CF8")}</div>
            <div class='pmc-value'>{unique_dbs}</div>
            <div class='pmc-label'>Databases</div>
        </div>
        """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════ #
    # 2. ACTIVITY TIMELINE
    # ═══════════════════════════════════════════════════════════════ #
    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>Activity Timeline</div>", unsafe_allow_html=True)

    def _format_event_time(ts_str: str) -> str:
        """Format timestamp into a relative or readable format."""
        import datetime
        try:
            dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            diff = datetime.datetime.now() - dt
            sec = diff.total_seconds()
            if sec < 0:
                return "Just now"
            if sec < 60:
                return "Just now"
            if sec < 3600:
                return f"{int(sec // 60)}m ago"
            if sec < 86400:
                return f"{int(sec // 3600)}h ago"
            return dt.strftime("%b %d, %Y %I:%M %p")
        except Exception:
            return ts_str

    from utils.settings_manager import get_setting
    timeline_events = get_setting("activity_timeline")
    if not isinstance(timeline_events, list) or not timeline_events:
        import datetime
        timeline_events = [{
            "text": "Profile page loaded",
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }]

    # Show timeline events in a clean container
    st.markdown("<div class='tab-settings-area' style='padding: 12px 20px; margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)
    for event in reversed(timeline_events[-6:]):
        display_time = _format_event_time(event["time"])
        st.markdown(f"""
        <div class='activity-item'>
            <div class='activity-dot'></div>
            <div style='flex-grow: 1;'>
                <div class='activity-text'>{event["text"]}</div>
                <div class='activity-time'>{display_time}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════ #
    # 3. ACCOUNT SETTINGS
    # ═══════════════════════════════════════════════════════════════ #
    st.markdown("<div class='section-header'>Account Settings</div>", unsafe_allow_html=True)

    tab_profile, tab_security = st.tabs(["Edit Profile", "Change Password"])

    with tab_profile:
        st.markdown("<div class='tab-settings-area'>", unsafe_allow_html=True)
        col_form, col_space = st.columns([2, 1])
        with col_form:
            with st.form("edit_profile_form", clear_on_submit=False):
                new_name = st.text_input("Full Name", value=profile.get("full_name") or "")
                new_email = st.text_input("Email", value=profile.get("email") or "")
                col_save, col_cancel = st.columns(2)
                save = col_save.form_submit_button("Save Changes", type="primary", use_container_width=True)
                cancel = col_cancel.form_submit_button("Cancel", use_container_width=True)

            if cancel:
                st.rerun()
            if save:
                result = update_user_profile(full_name=new_name, email=new_email)
                if result.get("success"):
                    st.session_state["user_profile"] = result.get("data", {})
                    st.session_state["_profile_updated"] = "Just now"
                    try:
                        from utils.settings_manager import log_activity
                        log_activity("Updated profile details (Name/Email)")
                    except Exception:
                        pass
                    st.success("Profile updated successfully.")
                    st.rerun()
                else:
                    st.error(result.get("error", "Could not update profile."))
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_security:
        st.markdown("<div class='tab-settings-area'>", unsafe_allow_html=True)
        st.caption("Password must be 8+ characters with uppercase, lowercase, a number, and a special character.")
        col_form2, col_space2 = st.columns([2, 1])
        with col_form2:
            with st.form("change_password_form", clear_on_submit=False):
                current_pw = st.text_input("Current Password", type="password")
                new_pw = st.text_input("New Password", type="password")
                confirm_pw = st.text_input("Confirm New Password", type="password")
                col_s2, col_c2 = st.columns(2)
                save2 = col_s2.form_submit_button("Update Password", type="primary", use_container_width=True)
                cancel2 = col_c2.form_submit_button("Cancel", use_container_width=True)

            if cancel2:
                st.rerun()
            if save2:
                if new_pw != confirm_pw:
                    st.error("New passwords do not match.")
                elif not current_pw or not new_pw:
                    st.error("Please fill in all password fields.")
                else:
                    result = change_password(current_pw, new_pw)
                    if result.get("success"):
                        try:
                            from utils.settings_manager import log_activity
                            log_activity("Updated account password")
                        except Exception:
                            pass
                        st.success("Password changed successfully.")
                        st.rerun()
                    else:
                        st.error(result.get("error", "Could not change password."))
        st.markdown("</div>", unsafe_allow_html=True)

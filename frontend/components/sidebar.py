"""
Sidebar — DataPilot AI
Modern AI workspace sidebar with fixed structure and scrollable query list.
"""
import re
from functools import lru_cache
import streamlit as st
from utils.icons import get_icon


# ─────────────────────────────────────────────────────────────────────────────
# Smart query title generator (client-side, no API needed)
# ─────────────────────────────────────────────────────────────────────────────
_STOP_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "should", "could", "may", "might",
    "me", "my", "we", "our", "you", "your", "it", "its", "this", "that",
    "by", "from", "with", "as", "into", "through", "during", "before",
    "after", "above", "below", "between", "each", "about", "show", "get",
    "find", "list", "give", "tell", "what", "which", "where", "how", "all",
    "more", "most", "other", "some", "such", "than", "then", "so", "can",
}

_INTENT_MAP = {
    r"\b(top|highest|best)\b.*\b(\d+)\b": "Top {0}",
    r"\bcompare\b": "Comparison",
    r"\btrend\b": "Trend Analysis",
    r"\brevenue\b": "Revenue",
    r"\bsales\b": "Sales",
    r"\baverage\b|\bavg\b": "Average",
    r"\btotal\b|\bsum\b": "Total",
    r"\bcount\b|\bhow many\b": "Count",
    r"\bdistribution\b|\bbreakdown\b": "Distribution",
    r"\bgrowth\b": "Growth",
    r"\brating\b|\brated\b": "Ratings",
    r"\bgenre\b": "By Genre",
    r"\bregion\b|\bcountry\b": "By Region",
    r"\byear\b|\bannual\b": "Annual",
    r"\bmonth\b|\bmonthly\b": "Monthly",
}


@lru_cache(maxsize=256)
def _smart_title(query: str) -> str:
    """Convert a full natural-language query into a short 3-5 word title."""
    if not query:
        return "Untitled Query"

    q = query.strip().lower()

    words = re.findall(r"[a-z_]+", q)
    keywords = [w.replace("_", " ").title() for w in words
                if w not in _STOP_WORDS and len(w) >= 4]

    intent_prefix = ""
    for pattern, label in _INTENT_MAP.items():
        m = re.search(pattern, q)
        if m:
            try:
                if "{0}" in label:
                    val = m.group(2) if len(m.groups()) >= 2 else (m.group(1) if m.groups() else "")
                    intent_prefix = label.format(val)
                else:
                    intent_prefix = label
            except (IndexError, AttributeError):
                intent_prefix = label
            break

    if intent_prefix:
        parts = [intent_prefix] + [k for k in keywords if k.lower() not in intent_prefix.lower()]
        title = " ".join(parts[:4])
    else:
        title = " ".join(keywords[:4])

    return title.strip() or query[:30].title()


def _dedupe_history(history: list) -> list:
    """Move repeated queries to top instead of duplicating entries."""
    seen_queries = {}
    result = []
    for item in reversed(history):
        q = item.get("query", "").strip().lower()
        if q not in seen_queries:
            seen_queries[q] = True
            result.append(item)
    return list(reversed(result))


def render_sidebar():
    with st.sidebar:
        # ── GLOBAL CSS ── #
        st.markdown("""
        <style>
        /* ── Safeguards to prevent horizontal scrolling and content clipping ── */
        section[data-testid="stSidebar"] {
            box-sizing: border-box !important;
        }
        section[data-testid="stSidebar"] div,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] button,
        section[data-testid="stSidebar"] a {
            max-width: 100% !important;
            box-sizing: border-box !important;
        }

        /* ── Sidebar container: full height flex column ── */
        section[data-testid="stSidebar"] > div:first-child {
            overflow: hidden !important;
            height: 100vh !important;
            padding: 0 !important;
        }
        [data-testid="stSidebarUserContent"] {
            height: 100vh !important;
            overflow: hidden !important;
            padding: 0 1rem 24px 1rem !important;
            display: flex !important;
            flex-direction: column !important;
            box-sizing: border-box !important;
        }
        /* Root vertical block must fill height and be flex too */
        [data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] {
            flex: 1 1 auto !important;
            display: flex !important;
            flex-direction: column !important;
            height: 100% !important;
            gap: 0 !important;
            overflow: hidden !important;
        }
        /* Reduce stSidebarHeader padding and position it absolutely over our custom header */
        [data-testid="stSidebarHeader"] {
            padding: 0 !important;
            min-height: 0 !important;
            position: absolute !important;
            top: 15px !important;
            right: 5px !important;
            z-index: 99999 !important;
            background: transparent !important;
        }

        /* ── TOP section items: don't grow, don't shrink away ── */
        [data-testid="stSidebarUserContent"] div.element-container:has(.dp-top-marker) ~ div[data-testid="stVerticalBlock"],
        [data-testid="stSidebarUserContent"] div.element-container:has(.dp-top-marker) {
            flex-shrink: 0 !important;
        }

        /* All direct element-containers in sidebar: shrink by default */
        [data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] > div.element-container {
            flex-shrink: 0 !important;
        }
        [data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {
            flex-shrink: 0 !important;
        }

        /* ── MIDDLE: the scrollable container (queries present) ── */
        [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-inner) {
            min-height: 0 !important;
            overflow: hidden !important;
            /* Grow to fill available space when queries are present */
            flex: 1 1 auto !important;
        }
        [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-inner) > div {
            overflow-y: auto !important;
            overflow-x: hidden !important;
            min-height: 0 !important;
        }
        [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-inner) > div::-webkit-scrollbar {
            width: 4px;
        }
        [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-inner) > div::-webkit-scrollbar-thumb {
            background: rgba(99,102,241,0.3);
            border-radius: 4px;
        }

        /* ── MIDDLE: collapse to auto height when empty (no queries) ── */
        [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-no-items) {
            flex: 0 0 auto !important;
            height: auto !important;
            min-height: 0 !important;
            max-height: none !important;
            overflow: visible !important;
        }
        [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-no-items) > div {
            height: auto !important;
            min-height: 0 !important;
            max-height: none !important;
            overflow: visible !important;
        }

        /* ── BOTTOM: profile — margin-top auto pushes it to bottom ── */
        [data-testid="stSidebarUserContent"] div.element-container:has(.dp-profile-start) {
            margin-top: auto !important;
            flex-shrink: 0 !important;
        }
        [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"]:has(.dp-profile-cols-marker) {
            flex-shrink: 0 !important;
        }

        /* ── Component styles ── */
        .dp-top-marker, .dp-rq-inner, .dp-rq-no-items, .dp-profile-start, .dp-profile-cols-marker { display: none !important; }

        .dp-brand-block { padding: 15px 0 12px 0; margin-top: 0; width: calc(100% - 35px); position: relative; z-index: 100; }
        .dp-brand-row { display:flex; align-items:center; gap:12px; }
        .dp-brand-icon {
            background: linear-gradient(135deg, #6366F1, #8B5CF6);
            border-radius: 8px; width:32px; height:32px;
            display:flex; align-items:center; justify-content:center;
            flex-shrink:0; box-shadow:0 3px 10px rgba(99,102,241,0.4); color:white;
        }
        .dp-brand-name {
            font-size:1.2rem; font-weight:800;
            color: #F8FAFC; letter-spacing: -0.5px; line-height:1.2;
        }
        .dp-nav-label {
            font-size:0.75rem; font-weight:700; color:#475569;
            text-transform:uppercase; letter-spacing:1px;
            padding: 14px 0 8px 0; margin-bottom: 2px;
            display: block;
        }
        .dp-db-card {
            background:rgba(15,23,42,0.7); border:1px solid rgba(99,102,241,0.2);
            border-radius:12px; padding:10px 14px; margin-top: 8px;
        }
        .dp-db-status-row { display:flex; align-items:center; gap:8px; }
        .dp-db-dot { width:8px; height:8px; background:#10B981; border-radius:50%; box-shadow:0 0 6px rgba(16,185,129,0.6); flex-shrink:0; }
        .dp-db-dot-off { width:8px; height:8px; background:#EF4444; border-radius:50%; flex-shrink:0; }
        .dp-db-name { font-size:0.82rem; font-weight:600; color:#E2E8F0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .dp-db-meta { font-size:0.7rem; color:#64748B; margin-top:2px; display:flex; align-items:center; gap:6px; }
        .dp-section-sep { border:none; border-top:1px solid #1E293B; margin:6px 0; }
        .dp-rq-empty { font-size:0.79rem; color:#475569; font-style:italic; padding:6px 0; }

        /* ── Profile card ── */
        .dp-profile-card {
            background: rgba(15,23,42,0.7);
            border: 1px solid rgba(99,102,241,0.2);
            border-radius: 16px 16px 0 0;
            padding: 12px 14px 8px 14px;
            margin-top: 16px !important;
            margin-bottom: 0;
            border-bottom: none;
        }
        .dp-profile-row { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
        .dp-profile-avatar {
            background:linear-gradient(135deg, #6366F1, #8B5CF6);
            border-radius:8px; width:32px; height:32px;
            display:flex; align-items:center; justify-content:center;
            font-size:14px; flex-shrink:0; color:white; font-weight:700;
        }
        .dp-profile-name {
            font-size: 0.85rem; font-weight: 600; color: #E2E8F0;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }
        .dp-profile-role { font-size:0.7rem; color:#64748B; }
        .dp-workspace-label {
            font-size: 0.7rem; color: #6366F1; font-weight: 600;
            letter-spacing: 0.5px; margin-top: 2px;
            display: block !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }

        /* Profile buttons fused below card */
        [data-testid="stSidebarUserContent"] div.element-container:has(.dp-profile-cols-marker) + div[data-testid="stHorizontalBlock"] {
            background: rgba(15,23,42,0.7);
            border: 1px solid rgba(99,102,241,0.2);
            border-top: 1px solid rgba(99,102,241,0.1) !important;
            border-radius: 0 0 16px 16px;
            padding: 6px 14px 14px 14px !important;
            margin-top: 0 !important;
            margin-bottom: 8px !important;
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 8px !important;
            width: 100% !important;
            max-width: 100% !important;
        }
        [data-testid="stSidebarUserContent"] div.element-container:has(.dp-profile-cols-marker) + div[data-testid="stHorizontalBlock"] > div {
            flex: 1 1 50% !important;
            min-width: 0 !important;
            width: 50% !important;
            max-width: 50% !important;
        }
        [data-testid="stSidebarUserContent"] div.element-container:has(.dp-profile-cols-marker) + div[data-testid="stHorizontalBlock"] button {
            background: rgba(99,102,241,0.06) !important;
            border: 1px solid rgba(99,102,241,0.15) !important;
            color: #E2E8F0 !important;
            border-radius: 6px !important;
            height: 32px !important;
            font-size: 0.78rem !important;
            padding: 0 4px !important;
            font-weight: 600 !important;
            justify-content: center !important;
            transition: all 0.2s ease !important;
        }
        [data-testid="stSidebarUserContent"] div.element-container:has(.dp-profile-cols-marker) + div[data-testid="stHorizontalBlock"] button:hover {
            background: rgba(99,102,241,0.15) !important;
            border-color: rgba(99,102,241,0.35) !important;
            color: white !important;
        }

        /* ── Sidebar nav buttons ── */
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
            padding: 0 0.6rem !important;
            overflow: hidden;
            width: 100%;
            margin-top: 4px;
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(99,102,241,0.1);
            color: #E2E8F0;
            border-color: rgba(99,102,241,0.2);
            transform: translateX(3px);
        }
        section[data-testid="stSidebar"] .stButton > button p {
            text-align: left; margin: 0;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            line-height: 2.2rem;
            color: inherit !important;
        }
        /* Active nav button */
        section[data-testid="stSidebar"] button[data-testid="baseButton-primary"] {
            background: linear-gradient(135deg, #6366F1, #8B5CF6) !important;
            color: #FFFFFF !important;
            border: none !important;
            font-weight: 600 !important;
            justify-content: flex-start !important;
        }
        section[data-testid="stSidebar"] button[data-testid="baseButton-primary"] p {
            color: #FFFFFF !important;
        }
        /* Remove gap between recent query items */
        [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlock"]:has(.dp-rq-inner) {
            gap: 2px !important;
        }

        /* ── Responsive Sidebar ── */
        @media (max-width: 768px) {
            /* Width & Height constraints on both stSidebar and its wrapper to prevent collapsing/clipping */
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
            [data-testid="stSidebarUserContent"] {
                height: 100vh !important;
                width: 100% !important;
                max-width: 100% !important;
                overflow: hidden !important;
                display: flex !important;
                flex-direction: column !important;
                padding: 0 0.75rem 20px 0.75rem !important;
                box-sizing: border-box !important;
            }
            [data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] {
                height: 100% !important;
                width: 100% !important;
                max-width: 100% !important;
                flex: 1 1 auto !important;
                display: flex !important;
                flex-direction: column !important;
                overflow: hidden !important;
                gap: 0 !important;
            }
            [data-testid="stSidebarHeader"] {
                padding: 0 !important;
                min-height: 0 !important;
                position: absolute !important;
                top: 8px !important;
                right: 8px !important;
                z-index: 999999 !important;
                background: transparent !important;
            }

            /* Branding compact on mobile */
            .dp-brand-block { padding: 12px 0 8px 0 !important; width: calc(100% - 50px) !important; }
            .dp-brand-name { font-size: 1.05rem !important; }
            .dp-brand-icon { width: 28px !important; height: 28px !important; }

            /* Navigation buttons: larger touch targets */
            section[data-testid="stSidebar"] .stButton > button {
                height: 2.5rem !important;
                min-height: 2.5rem !important;
                font-size: 0.85rem !important;
            }

            /* DB card compact */
            .dp-db-card { padding: 8px 10px !important; margin-top: 6px !important; }

            /* Queries present: scrollable up to max-height */
            [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-inner):not(:has(.dp-rq-no-items)) {
                max-height: 150px !important;
            }
            [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-inner):not(:has(.dp-rq-no-items)) > div {
                max-height: 150px !important;
                width: 100% !important;
                max-width: 100% !important;
            }

            /* Empty state: collapse fully on mobile too */
            [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-no-items) {
                height: auto !important;
                max-height: none !important;
            }
            [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-no-items) > div {
                height: auto !important;
                max-height: none !important;
            }

            /* Profile card compact */
            .dp-profile-card { padding: 10px 12px 6px 12px !important; margin-top: 12px !important; }
            .dp-profile-avatar { width: 28px !important; height: 28px !important; font-size: 12px !important; }
            .dp-profile-name {
                font-size: 0.8rem !important;
                white-space: nowrap !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
            }

            /* Profile buttons layout consistency */
            [data-testid="stSidebarUserContent"] div.element-container:has(.dp-profile-cols-marker) + div[data-testid="stHorizontalBlock"] {
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: nowrap !important;
                gap: 8px !important;
                width: 100% !important;
                max-width: 100% !important;
            }
            [data-testid="stSidebarUserContent"] div.element-container:has(.dp-profile-cols-marker) + div[data-testid="stHorizontalBlock"] > div {
                flex: 1 1 50% !important;
                min-width: 0 !important;
                width: 50% !important;
                max-width: 50% !important;
            }
        }
        @media (max-width: 480px) {
            [data-testid="stSidebarUserContent"] {
                padding: 0 0.5rem 12px 0.5rem !important;
            }
            .dp-brand-block { padding: 8px 0 4px 0 !important; }
            .dp-brand-row { gap: 6px !important; }
            .dp-brand-name { font-size: 0.95rem !important; }
            .dp-brand-icon { width: 24px !important; height: 24px !important; }
            section[data-testid="stSidebar"] .stButton > button {
                height: 2.1rem !important;
                min-height: 2.1rem !important;
                font-size: 0.78rem !important;
            }
            .dp-db-card { padding: 6px 8px !important; margin-top: 4px !important; }
            [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-inner):not(:has(.dp-rq-no-items)) {
                max-height: 120px !important;
            }
            [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.dp-rq-inner):not(:has(.dp-rq-no-items)) > div {
                max-height: 120px !important;
            }
            .dp-profile-card { padding: 6px 10px 4px 10px !important; margin-top: 8px !important; }
            .dp-profile-avatar { width: 24px !important; height: 24px !important; font-size: 10px !important; }
            .dp-profile-name {
                font-size: 0.76rem !important;
            }
        }
        </style>
        """, unsafe_allow_html=True)

        # ══════════════════════════════════════════
        # 1. TOP — branding + nav + db status
        # ══════════════════════════════════════════
        st.markdown("<span class='dp-top-marker'></span>", unsafe_allow_html=True)

        logo_svg = get_icon("compass", size=20, color="white", stroke_width=2.0)
        st.markdown(f"""
        <div class='dp-brand-block'>
            <div class='dp-brand-row'>
                <div class='dp-brand-icon'>{logo_svg}</div>
                <div class='dp-brand-name'>DataPilot AI</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div class='dp-nav-label'>Workspace</div>", unsafe_allow_html=True)
        current_menu = st.session_state.get("menu", "Dashboard")

        dash_type = "primary" if current_menu == "Dashboard" else "secondary"
        if st.button("New Chat", key="nav_Dashboard", use_container_width=True, type=dash_type):
            st.session_state["menu"] = "Dashboard"
            st.query_params["page"] = "Dashboard"
            st.rerun()

        past_type = "primary" if current_menu == "Recent Connections" else "secondary"
        if st.button("Recent Connections", key="nav_PastConnections", use_container_width=True, type=past_type):
            st.session_state["menu"] = "Recent Connections"
            st.query_params["page"] = "Recent Connections"
            st.rerun()

        # DB Status Card
        if st.session_state.get("connected"):
            db_info = st.session_state.get("db_info", {})
            db_type = db_info.get("database_type", db_info.get("db_type", "")).lower()
            raw_name = (db_info.get("source_filename") or db_info.get("database") or "Dataset")
            import re as _re
            clean = _re.split(r"[/\\]", str(raw_name))[-1]
            clean = _re.sub(r"\.(db|sqlite|sqlite3|csv)$", "", clean, flags=_re.IGNORECASE)
            clean = _re.sub(r"^\d+\s+", "", clean.replace("_", " ").replace("-", " ")).strip()
            display_name = clean.title() if clean else "Dataset"
            db_svg = get_icon(db_type, size=14, color="#A78BFA")
            display_type = "FILE" if db_type in ("sqlite", "sqlite3", "file") else db_type.upper()
            st.markdown(f"""
            <div class='dp-db-card'>
                <div class='dp-db-status-row'>
                    <div class='dp-db-dot'></div>
                    <div class='dp-db-name'>{display_name}</div>
                </div>
                <div class='dp-db-meta'>{db_svg} {display_type} &bull; Active</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            db_svg = get_icon("database", size=14, color="#64748B")
            st.markdown(f"""
            <div class='dp-db-card'>
                <div class='dp-db-status-row'>
                    <div class='dp-db-dot-off'></div>
                    <div class='dp-db-name' style='color:#94A3B8;'>No Dataset</div>
                </div>
                <div class='dp-db-meta'>{db_svg} Connect to begin</div>
            </div>
            """, unsafe_allow_html=True)


        st.markdown("<hr class='dp-section-sep'>", unsafe_allow_html=True)
        st.markdown("<div class='dp-nav-label'>Recent Queries</div>", unsafe_allow_html=True)

        # ══════════════════════════════════════════
        # 2. MIDDLE — scrollable recent queries
        # ══════════════════════════════════════════
        if not st.session_state.get("connected"):
            history = []
        else:
            db_info = st.session_state.get("db_info", {})
            current_db = db_info.get("database", "")
            history = [
                item for item in st.session_state.get("query_history", [])
                if item.get("database_name") == current_db
            ]
        deduped = _dedupe_history(history)

        # Always render inside st.container so CSS :has(.dp-rq-inner) consistently
        # targets a stVerticalBlockBorderWrapper. The marker class switches between
        # dp-rq-inner (queries present → flex-grow + scroll) and dp-rq-no-items
        # (empty → height:auto, no dead space).
        _container_height = 230 if deduped else 1  # height=1 collapses; CSS overrides to auto
        with st.container(height=_container_height, border=False):
            marker_class = "dp-rq-inner" if deduped else "dp-rq-inner dp-rq-no-items"
            st.markdown(f"<span class='{marker_class}'></span>", unsafe_allow_html=True)

            if not deduped:
                st.markdown(
                    "<div class='dp-rq-empty'>Your AI queries will appear here after you run them.</div>",
                    unsafe_allow_html=True,
                )
            else:
                for i, item in enumerate(reversed(deduped[-50:])):
                    q = item.get("query", "")
                    title = item.get("title") or _smart_title(q)
                    display = title if len(title) <= 45 else title[:42] + "..."

                    if st.button(display, key=f"rq_restore_{i}", use_container_width=True):
                        st.session_state["current_query"] = q
                        st.session_state["menu"] = "Dashboard"
                        st.query_params["page"] = "Dashboard"
                        cached_result = item.get("result")
                        if cached_result:
                            st.session_state["last_result"] = cached_result
                            st.session_state["should_scroll"] = True
                            st.session_state["is_generating"] = False
                        else:
                            st.session_state["pending_query"] = q
                            st.session_state["is_generating"] = True
                        st.rerun()

        st.markdown("<hr class='dp-section-sep'>", unsafe_allow_html=True)

        # ══════════════════════════════════════════
        # 3. BOTTOM — profile card pinned to bottom
        # ══════════════════════════════════════════
        st.markdown("<span class='dp-profile-start'></span>", unsafe_allow_html=True)

        user_info = st.session_state.get("user_profile", {"username": "Guest"})
        username = user_info.get("username", "Guest")
        role = str(user_info.get("role", "user")).capitalize()
        initials = username[0].upper() if username else "G"
        sparkle_svg = get_icon("sparkles", size=11, color="#8B5CF6")

        st.markdown(f"""
        <div class='dp-profile-card'>
            <div class='dp-profile-row'>
                <div class='dp-profile-avatar'>{initials}</div>
                <div style='flex-grow: 1;'>
                    <div class='dp-profile-name'>{username}</div>
                    <div class='dp-profile-role'>{role}</div>
                </div>
            </div>
            <div class='dp-workspace-label'>{sparkle_svg} AI Analytics Workspace</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<span class='dp-profile-cols-marker'></span>", unsafe_allow_html=True)
        col_p, col_s = st.columns(2)
        with col_p:
            if st.button("Profile", key="sb_profile", use_container_width=True):
                st.session_state["menu"] = "Profile"
                st.query_params["page"] = "Profile"
                st.rerun()
        with col_s:
            if st.button("Settings", key="sb_settings", use_container_width=True):
                st.session_state["menu"] = "Settings"
                st.query_params["page"] = "Settings"
                st.rerun()
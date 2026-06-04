"""
Recent Connections — DataPilot AI
Premium SaaS database history and quick reconnect workspace.
"""
import streamlit as st
from components.sidebar import render_sidebar
from utils.connection_manager import (
    get_saved_connections,
    delete_saved_connection,
    toggle_favorite,
    reconnect_database,
    get_relative_time
)
from utils.icons import get_icon

# ─────────────────────────────────────────────────────────────────────────────
# CSS Design tokens for premium cards
# ─────────────────────────────────────────────────────────────────────────────
_CONNECTIONS_CSS = """
<style>
/* ────────── STYLE STREAMLIT NATIVE CONTAINER AS THE CARD ────────── */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title):not(:has(div[data-testid="stVerticalBlockBorderWrapper"])) {
    background: linear-gradient(135deg, rgba(15,23,42,0.95), rgba(30,41,59,0.75)) !important;
    border: 1px solid rgba(99,102,241,0.18) !important;
    border-radius: 14px !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25) !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    margin-bottom: 8px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title):not(:has(div[data-testid="stVerticalBlockBorderWrapper"])):hover {
    border-color: rgba(99,102,241,0.45) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(99,102,241,0.22) !important;
}

.conn-badge {
    font-size: 0.68rem;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}
/* Reduce native container padding to make card smaller */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title):not(:has(div[data-testid="stVerticalBlockBorderWrapper"])) > div > div[data-testid="stVerticalBlock"] {
    padding: 12px !important;
    gap: 0.25rem !important;
}
.conn-badge.mysql {
    background: rgba(0, 117, 143, 0.12);
    color: #38BDF8;
    border: 1px solid rgba(0, 117, 143, 0.35);
}
.conn-badge.postgresql, .conn-badge.postgres {
    background: rgba(51, 103, 145, 0.12);
    color: #60A5FA;
    border: 1px solid rgba(51, 103, 145, 0.35);
}
.conn-badge.sqlite, .conn-badge.file {
    background: rgba(139, 92, 246, 0.12);
    color: #A78BFA;
    border: 1px solid rgba(139, 92, 246, 0.35);
}
.conn-card-title {
    font-size: 1.15rem;
    font-weight: 800;
    color: #F8FAFC;
    margin-top: -12px;
    margin-bottom: 8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    letter-spacing: -0.3px;
}
.conn-card-info {
    font-size: 0.8rem;
    color: #94A3B8;
    margin-bottom: 5px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.conn-card-footer {
    font-size: 0.72rem;
    color: #64748B;
    margin-top: 12px;
    border-top: 1px solid rgba(51, 65, 85, 0.25);
    padding-top: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.conn-usage-badge {
    background: rgba(99,102,241,0.08);
    border: 1px solid rgba(99,102,241,0.15);
    color: #A5B4FC;
    padding: 2px 6px;
    border-radius: 6px;
    font-size: 0.68rem;
    font-weight: 600;
}

/* ────────── NATIVE STAR BUTTON STRIPPED STYLING ────────── */
.star-button-marker {
    display: none !important;
}
/* Style star button inside its leaf column containing the star marker */
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker) button {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    border-color: transparent !important;
    box-shadow: none !important;
    outline: none !important;
    padding: 0 !important;
    width: 32px !important;
    height: 32px !important;
    min-width: 32px !important;
    min-height: 32px !important;
    cursor: pointer !important;
    float: right !important;
    text-align: right !important;
    justify-content: flex-end !important;
    transform: none !important;
    transition: transform 0.2s ease !important;
    font-size: 1.45rem !important;
}
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker) button p,
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker) button span {
    font-size: 1.45rem !important;
}
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker) button:hover {
    transform: scale(1.2) !important;
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    border-color: transparent !important;
}
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker) button:active {
    transform: scale(0.95) !important;
    background: transparent !important;
}
/* Color for unfavorited star */
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker.unfavorited) button,
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker.unfavorited) button p,
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker.unfavorited) button span {
    color: #64748B !important; /* Grey/slate */
}
/* Color for favorited star */
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker.favorited) button,
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker.favorited) button p,
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker.favorited) button span {
    color: #F59E0B !important; /* Yellow/amber */
}
/* Optimize spacing for native columns in the header */
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.star-button-marker) {
    display: flex !important;
    justify-content: flex-end !important;
    align-items: center !important;
}

/* Hide the empty markdown blocks to prevent vertical gaps */
div.element-container:has(.delete-button-marker),
div.element-container:has(.star-button-marker) {
    display: none !important;
    margin: 0 !important;
    padding: 0 !important;
    height: 0 !important;
}

/* ────────── PREMIUM SAAS RED DELETE BUTTON ────────── */
.delete-button-marker {
    display: none !important;
}
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.delete-button-marker) button {
    color: #EF4444 !important;
    border-color: rgba(239, 68, 68, 0.4) !important;
    background: rgba(239, 68, 68, 0.08) !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.delete-button-marker) button p,
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.delete-button-marker) button span {
    color: #EF4444 !important;
    white-space: nowrap !important;
}
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.delete-button-marker) button:hover {
    color: #FFFFFF !important;
    background: #EF4444 !important;
    border-color: #EF4444 !important;
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.35) !important;
    transform: translateY(-1px) !important;
}
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.delete-button-marker) button:hover p,
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.delete-button-marker) button:hover span {
    color: #FFFFFF !important;
}
div[data-testid="stColumn"]:not(:has(div[data-testid="stColumn"])):has(.delete-button-marker) button:active {
    transform: translateY(0px) !important;
}

/* Page Header styling */
.conn-header-wrapper {
    margin-bottom: 0px;
}
.conn-title {
    font-size: 2.25rem !important;
    font-weight: 700 !important;
    color: #FFFFFF !important;
    margin: 0 0 8px 0 !important;
    line-height: 1.2 !important;
}
.conn-desc-desktop {
    font-size: 1rem !important;
    color: #475569 !important;
    margin: 0 !important;
    line-height: 1.5 !important;
}
.conn-desc-mobile {
    display: none !important;
}
.conn-card-spacing {
    height: 12px;
}
.conn-button-spacing {
    height: 18px;
}

/* ── Responsive Connections ── */
@media (max-width: 1024px) {
    .conn-card-title { font-size: 1rem !important; }
    .conn-card-info { font-size: 0.75rem !important; }
}
@media (max-width: 768px) {
    div[data-testid="stAppViewBlockContainer"],
    div.block-container {
        padding-left: 14px !important;
        padding-right: 14px !important;
    }

    .conn-title {
        font-size: 1.25rem !important;
        margin-bottom: 4px !important;
    }
    .conn-desc-desktop {
        display: none !important;
    }
    .conn-desc-mobile {
        display: block !important;
        font-size: 0.78rem !important;
        color: #94A3B8 !important;
        margin: 0 !important;
        line-height: 1.3 !important;
    }
    .conn-divider {
        margin: 8px 0 12px 0 !important;
    }
    .conn-card-spacing {
        height: 6px !important;
    }
    .conn-button-spacing {
        height: 10px !important;
    }

    /* Stack search and sort controls vertically with full-width inputs */
    div[data-testid="stHorizontalBlock"]:has(input[placeholder*="Search by Database Name"]) {
        display: flex !important;
        flex-direction: column !important;
        flex-wrap: nowrap !important;
        gap: 10px !important;
        margin-bottom: 12px !important;
        width: 100% !important;
    }
    div[data-testid="stHorizontalBlock"]:has(input[placeholder*="Search by Database Name"]) > div[data-testid="stColumn"] {
        flex: 1 1 100% !important;
        width: 100% !important;
        max-width: 100% !important;
    }
    
    /* Make search and dropdown text sizes compact on mobile */
    div[data-testid="stHorizontalBlock"]:has(input[placeholder*="Search by Database Name"]) input,
    div[data-testid="stHorizontalBlock"]:has(input[placeholder*="Search by Database Name"]) select,
    div[data-testid="stHorizontalBlock"]:has(input[placeholder*="Search by Database Name"]) div[data-baseweb="select"] * {
        font-size: 0.8rem !important;
    }

    /* Force columns of cards grid to display in a single vertical column with no horizontal scroll */
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stColumn"]:has(div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title))) {
        display: flex !important;
        flex-direction: column !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        gap: 12px !important;
    }
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stColumn"]:has(div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title))) > div[data-testid="stColumn"] {
        width: 100% !important;
        max-width: 100% !important;
        flex: 1 1 100% !important;
    }

    /* Force card header (badge + star button) to be side-by-side */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title) div[data-testid="stHorizontalBlock"]:has(.star-button-marker) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        justify-content: space-between !important;
        align-items: center !important;
        gap: 8px !important;
        width: 100% !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title) div[data-testid="stHorizontalBlock"]:has(.star-button-marker) > div[data-testid="stColumn"]:first-child {
        flex: 1 1 auto !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title) div[data-testid="stHorizontalBlock"]:has(.star-button-marker) > div[data-testid="stColumn"]:last-child {
        flex: 0 0 auto !important;
        width: 32px !important;
    }

    /* Force card footer buttons (Connect + Delete) to stack vertically inside the card */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title) div[data-testid="stHorizontalBlock"]:has(.delete-button-marker) {
        display: flex !important;
        flex-direction: column !important;
        gap: 8px !important;
        width: 100% !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title) div[data-testid="stHorizontalBlock"]:has(.delete-button-marker) > div[data-testid="stColumn"] {
        width: 100% !important;
        max-width: 100% !important;
        flex: 1 1 100% !important;
    }

    /* Reduce height of connect and delete buttons inside cards on mobile */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title) button {
        height: 32px !important;
        line-height: 32px !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        font-size: 0.78rem !important;
        border-radius: 8px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title) button p,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title) button span {
        font-size: 0.78rem !important;
    }

    .conn-card-title { font-size: 0.88rem !important; margin-top: -6px !important; }
    .conn-card-info {
        font-size: 0.7rem !important;
        gap: 5px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    .conn-card-footer { font-size: 0.65rem !important; padding-top: 8px !important; margin-top: 8px !important; }
    .conn-badge { font-size: 0.6rem !important; padding: 2px 6px !important; }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title):not(:has(div[data-testid="stVerticalBlockBorderWrapper"])) > div > div[data-testid="stVerticalBlock"] {
        padding: 8px !important;
        gap: 0.15rem !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title):not(:has(div[data-testid="stVerticalBlockBorderWrapper"])) {
        margin-bottom: 8px !important;
        border-radius: 10px !important;
    }
}
@media (max-width: 480px) {
    div[data-testid="stAppViewBlockContainer"],
    div.block-container {
        padding-left: 10px !important;
        padding-right: 10px !important;
    }

    .conn-title {
        font-size: 1.15rem !important;
    }
    .conn-desc-mobile {
        font-size: 0.74rem !important;
    }
    
    /* Make search and dropdown text sizes even smaller on micro screen */
    div[data-testid="stHorizontalBlock"]:has(input[placeholder*="Search by Database Name"]) input,
    div[data-testid="stHorizontalBlock"]:has(input[placeholder*="Search by Database Name"]) select,
    div[data-testid="stHorizontalBlock"]:has(input[placeholder*="Search by Database Name"]) div[data-baseweb="select"] * {
        font-size: 0.75rem !important;
    }

    /* Even more compact on micro viewports */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title) button {
        height: 28px !important;
        line-height: 28px !important;
        font-size: 0.72rem !important;
        border-radius: 6px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title) button p,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title) button span {
        font-size: 0.72rem !important;
    }

    .conn-card-title { font-size: 0.8rem !important; margin-top: -8px !important; }
    .conn-card-info {
        font-size: 0.65rem !important;
        gap: 3px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    .conn-card-footer { font-size: 0.6rem !important; padding-top: 6px !important; margin-top: 6px !important; }
    .conn-badge { font-size: 0.55rem !important; padding: 1px 4px !important; }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title):not(:has(div[data-testid="stVerticalBlockBorderWrapper"])) > div > div[data-testid="stVerticalBlock"] {
        padding: 6px !important;
        gap: 0.1rem !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.conn-card-title):not(:has(div[data-testid="stVerticalBlockBorderWrapper"])) {
        margin-bottom: 6px !important;
        border-radius: 8px !important;
    }
}
</style>
"""

@st.dialog("Quick Reconnect to Database")
def render_reconnect_modal(conn):
    """Modern modal dialog requesting only the password to initiate reconnect."""
    
    # Inject capsule styling directly inside the modal dialog container
    st.markdown("""
    <style>
    /* Target ONLY the Connect button (the ultimate bulletproof selector list for stModal and role="dialog") */
    div[role="dialog"] button[data-testid*="primary"],
    div[role="dialog"] button[data-testid^="baseButton-primary"],
    div[role="dialog"] button[kind="primary"],
    [role="dialog"] button[data-testid*="primary"],
    [role="dialog"] button[data-testid^="baseButton-primary"],
    [role="dialog"] button[kind="primary"],
    div[role="dialog"] div[data-testid="column"]:nth-of-type(2) button,
    div[role="dialog"] div[data-testid="column"]:nth-child(2) button,
    div[data-testid="stModal"] div[data-testid="column"]:nth-of-type(2) button,
    [data-testid="stModal"] div[data-testid="column"]:nth-of-type(2) button,
    div[role="dialog"] button:nth-of-type(3),
    div[role="dialog"] button:nth-of-type(2),
    div[data-testid="stModal"] button:nth-of-type(3),
    div[data-testid="stModal"] button:nth-of-type(2),
    [role="dialog"] button:nth-of-type(3),
    [role="dialog"] button:nth-of-type(2) {
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
    div[role="dialog"] button[data-testid*="primary"]:hover,
    div[role="dialog"] button[data-testid^="baseButton-primary"]:hover,
    div[role="dialog"] button[kind="primary"]:hover,
    [role="dialog"] button[data-testid*="primary"]:hover,
    [role="dialog"] button[data-testid^="baseButton-primary"]:hover,
    [role="dialog"] button[kind="primary"]:hover,
    div[role="dialog"] div[data-testid="column"]:nth-of-type(2) button:hover,
    div[role="dialog"] div[data-testid="column"]:nth-child(2) button:hover,
    div[data-testid="stModal"] div[data-testid="column"]:nth-of-type(2) button:hover,
    [data-testid="stModal"] div[data-testid="column"]:nth-of-type(2) button:hover,
    div[role="dialog"] button:nth-of-type(3):hover,
    div[role="dialog"] button:nth-of-type(2):hover,
    div[data-testid="stModal"] button:nth-of-type(3):hover,
    div[data-testid="stModal"] button:nth-of-type(2):hover,
    [role="dialog"] button:nth-of-type(3):hover,
    [role="dialog"] button:nth-of-type(2):hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 22px rgba(139,92,246,0.5) !important;
        background: linear-gradient(135deg, #9333EA, #8B5CF6) !important;
        color: #FFFFFF !important;
    }

    /* ── Hide Input Instructions Overlap ── */
    div[role="dialog"] div[data-testid="InputInstructions"],
    div[data-testid="stModal"] div[data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }

    /* ── Blurred, Lighter Backdrop Overlay ── */
    div[data-testid="stModal"] {
        background-color: rgba(15, 23, 42, 0.45) !important;
        backdrop-filter: blur(6px) !important;
        -webkit-backdrop-filter: blur(6px) !important;
    }

    /* ── Responsive Quick Reconnect Modal ── */
    div[role="dialog"],
    div[data-testid="stModal"] {
        padding: 20px 16px !important;
    }
    div[role="dialog"] h3 {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        color: #F8FAFC !important;
        margin-top: 4px !important;
    }
    div[role="dialog"] div[data-baseweb="input"] input {
        font-size: 0.85rem !important;
        height: 38px !important;
    }
    div[role="dialog"] div[data-testid="stWidgetLabel"] p,
    div[role="dialog"] label p {
        font-size: 0.78rem !important;
    }
    div[role="dialog"] button,
    div[role="dialog"] button[data-testid*="primary"],
    div[role="dialog"] button[data-testid^="baseButton-primary"],
    div[role="dialog"] button[kind="primary"] {
        height: 38px !important;
        line-height: 38px !important;
        font-size: 0.82rem !important;
        border-radius: 8px !important;
    }
    div[role="dialog"] button p,
    div[role="dialog"] button span {
        font-size: 0.82rem !important;
    }

    @media (max-width: 768px) {
        /* Mobile floating sheet layout - lightweight reconnect dialog */
        div[role="dialog"] {
            position: fixed !important;
            bottom: 20px !important;
            left: 16px !important;
            right: 16px !important;
            margin: 0 auto !important;
            width: calc(100% - 32px) !important;
            max-width: calc(100% - 32px) !important;
            border-radius: 16px !important;
            border: 1px solid rgba(99, 102, 241, 0.2) !important;
            background-color: #0F172A !important;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6) !important;
            padding: 16px !important;
            min-height: auto !important;
            height: auto !important;
        }

        /* Smaller close icon */
        div[role="dialog"] button[aria-label="Close"] {
            top: 12px !important;
            right: 12px !important;
            transform: scale(0.85) !important;
        }

        /* Compact titles & header spacing */
        div[role="dialog"] h3 {
            font-size: 1.1rem !important;
            margin-top: 0px !important;
            margin-bottom: 4px !important;
        }
        div[role="dialog"] .modal-metadata-strip {
            margin-bottom: 10px !important;
            font-size: 0.78rem !important;
        }
        div[role="dialog"] div[data-testid="stForm"] {
            padding: 10px !important;
            border-radius: 10px !important;
            background: rgba(30, 41, 59, 0.35) !important;
            border: 1px solid rgba(99, 102, 241, 0.1) !important;
        }
        div[role="dialog"] div[data-baseweb="input"] input {
            height: 36px !important;
            font-size: 0.8rem !important;
        }
    }

    @media (max-width: 480px) {
        div[role="dialog"] {
            bottom: 12px !important;
            left: 10px !important;
            right: 10px !important;
            width: calc(100% - 20px) !important;
            max-width: calc(100% - 20px) !important;
            border-radius: 12px !important;
            padding: 12px !important;
        }
        div[role="dialog"] h3 {
            font-size: 0.98rem !important;
        }
        div[role="dialog"] .modal-metadata-strip {
            margin-bottom: 8px !important;
            font-size: 0.72rem !important;
        }
        div[role="dialog"] div[data-testid="stForm"] {
            padding: 8px !important;
            border-radius: 8px !important;
        }
        div[role="dialog"] div[data-baseweb="input"] input {
            height: 32px !important;
            font-size: 0.76rem !important;
        }
        div[role="dialog"] div[data-testid="stWidgetLabel"] p,
        div[role="dialog"] label p {
            font-size: 0.72rem !important;
        }
        div[role="dialog"] button,
        div[role="dialog"] button[data-testid*="primary"],
        div[role="dialog"] button[data-testid^="baseButton-primary"],
        div[role="dialog"] button[kind="primary"] {
            height: 32px !important;
            line-height: 32px !important;
            font-size: 0.76rem !important;
            border-radius: 6px !important;
        }
        div[role="dialog"] button p,
        div[role="dialog"] button span {
            font-size: 0.76rem !important;
        }
        /* Stack buttons vertically on micro viewport dialog forms */
        div[role="dialog"] div[data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: column !important;
            gap: 6px !important;
            width: 100% !important;
        }
        div[role="dialog"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            max-width: 100% !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    db_type = conn.get('database_type', '').lower()
    st.markdown(f"### Reconnect to **{conn.get('database', 'Database')}**")
    if db_type in ("sqlite", "sqlite3", "file"):
        meta_html = f"FILE &bull; {conn.get('file_path', 'Local File')}"
    else:
        meta_html = f"{conn.get('database_type', '').upper()} &bull; {conn.get('username', '')}@{conn.get('host', '')}:{conn.get('port', '')}"
        
    st.markdown(
        f"<div class='modal-metadata-strip' style='font-size:0.82rem; color:#64748B; margin-bottom:16px;'>"
        f"{meta_html}"
        f"</div>",
        unsafe_allow_html=True
    )

    # Use standard Streamlit form to support Enter key submission natively!
    with st.form(key="reconnect_password_form", clear_on_submit=False):
        password = st.text_input(
            "Enter Database Password",
            type="password",
            placeholder="••••••••",
            help="Please input the database authentication password."
        )
        
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        
        col_cancel, col_connect = st.columns(2)
        with col_cancel:
            # st.form_submit_button close the form but we handle cancel manually
            cancel_clicked = st.form_submit_button("Cancel", use_container_width=True)
        with col_connect:
            connect_clicked = st.form_submit_button("Connect", type="primary", use_container_width=True)

        if connect_clicked:
            if not password:
                st.error("Authentication failed: Password cannot be blank.")
            else:
                with st.spinner("Establishing secure connection..."):
                    success, msg = reconnect_database(conn, password)
                
                if success:
                    st.success("Connected successfully!")
                    st.toast("🚀 Database loaded! Redirecting to Dashboard...")
                    # Automatically redirect to main workspace dashboard
                    st.session_state["menu"] = "Dashboard"
                    st.query_params["page"] = "Dashboard"
                    st.rerun()
                else:
                    st.error(f"Connection Failed: {msg}")
                    
        if cancel_clicked:
            st.rerun()

def show_past_connections():
    """Renders the central Recent Connections page."""
    # Ensure sidebar is rendered first
    render_sidebar()
    
    # Inject CSS
    st.markdown(_CONNECTIONS_CSS, unsafe_allow_html=True)

    # ── Page Header ──
    st.markdown(
        "<div class='conn-header-wrapper'>"
        "  <h1 class='conn-title'>Recent Connections</h1>"
        "  <p class='conn-desc-desktop'>Manage and reconnect to your configured enterprise data sources. "
        "For security and compliance, authentication credentials are not persisted locally.</p>"
        "  <p class='conn-desc-mobile'>Manage and reconnect to your databases.</p>"
        "</div>",
        unsafe_allow_html=True
    )

    st.markdown("<hr class='conn-divider' style='border:none; border-top:1px solid #1E293B; margin: 12px 0 20px 0;'>", unsafe_allow_html=True)

    # Load connections history list
    saved_connections = get_saved_connections()

    if not saved_connections:
        # Empty state screen
        st.markdown(
            "<div style='text-align:center; padding: 60px 20px; background: rgba(15,23,42,0.4); border-radius:16px; border: 1px dashed rgba(99,102,241,0.2);'>"
            "<h3 style='color: #94A3B8;'>No Database Connections History</h3>"
            "<p style='color: #64748B; font-size:0.9rem; margin-top:8px; margin-bottom:20px;'>"
            "Your database connections (MySQL and PostgreSQL) will automatically be saved here once initialized."
            "</p>"
            "</div>",
            unsafe_allow_html=True
        )
        if st.button("Connect New Database Now", type="primary"):
            st.session_state["menu"] = "Dashboard"
            st.query_params["page"] = "Dashboard"
            st.rerun()
        return

    # ── Search & Filter Controls bar ──
    ctrl_search, ctrl_sort = st.columns([3, 1])
    with ctrl_search:
        search_query = st.text_input(
            "Search connections",
            placeholder="Search by Database Name, Host, Port, Username...",
            label_visibility="collapsed"
        )
    with ctrl_sort:
        sort_by = st.selectbox(
            "Sort by",
            ["Recently Connected", "Most Used", "Database Name"],
            label_visibility="collapsed"
        )

    # ── Filter & Sort Logic ──
    filtered_connections = []
    for conn in saved_connections:
        match_parts = [
            conn.get('database', ''),
            conn.get('host', ''),
            conn.get('username', ''),
            conn.get('database_type', ''),
            conn.get('source_filename', ''),
            conn.get('file_path', '')
        ]
        match_str = " ".join(str(part) for part in match_parts if part).lower()
        if not search_query or search_query.lower() in match_str:
            filtered_connections.append(conn)

    # Re-sort list based on selectbox
    if sort_by == "Most Used":
        filtered_connections.sort(key=lambda x: x.get("usage_count", 0), reverse=True)
    elif sort_by == "Database Name":
        filtered_connections.sort(key=lambda x: x.get("database", "").lower())
    else:
        # Default: Recently Connected (Favorites pinned first, then recency)
        # The connection_manager get_saved_connections is already sorting favorites first, then recency
        # But if we did search/filter, let's keep that default sorting sequence
        pass

    if not filtered_connections:
        st.info("No connections match your search query.")
        return

    # ── Connections Cards Grid ──
    # Arrange cards in rows of 3 to maintain correct chronological stacking on mobile
    for i in range(0, len(filtered_connections), 3):
        row_conns = filtered_connections[i:i+3]
        cols = st.columns(3, gap="medium")
        for col_idx, conn in enumerate(row_conns):
            with cols[col_idx]:
                relative_time = get_relative_time(conn.get("last_connected"))
                is_fav = conn.get("is_favorite", False)
                fav_emoji = "★" if is_fav else "☆"
                fav_color = "#F59E0B" if is_fav else "#64748B"
                
                # HTML Card natively rendered inside st.container(border=True)
                with st.container(border=True):
                    # Header row: Badge on left, native star button on right
                    header_col1, header_col2 = st.columns([5, 1])
                    with header_col1:
                        db_type = conn['database_type'].lower()
                        display_type = "FILE" if db_type in ("sqlite", "sqlite3", "file") else db_type.upper()
                        icon_svg = get_icon(db_type, size=14, color="currentColor")
                        st.markdown(f"<span class='conn-badge {db_type}'>{icon_svg} {display_type}</span>", unsafe_allow_html=True)
                    with header_col2:
                        # Dynamically set active (yellow) vs inactive (grey) color using scoped classes
                        fav_class = "favorited" if is_fav else "unfavorited"
                        st.markdown(f'<div class="star-button-marker {fav_class}" id="star-marker-{conn["id"]}"></div>', unsafe_allow_html=True)
                        if st.button(fav_emoji, key=f"star_{conn['id']}", help="Pin connection to top"):
                            toggle_favorite(conn["id"])
                            st.rerun()

                    # Card Content
                    st.markdown(f"<div class='conn-card-title' title='{conn.get('database', 'Database')}'>{conn.get('database', 'Database')}</div>", unsafe_allow_html=True)
                    if db_type in ("sqlite", "sqlite3", "file"):
                        file_svg = get_icon("file-text", size=14, color="#64748B")
                        loc_svg = get_icon("map-pin", size=14, color="#64748B")
                        st.markdown(f"<div class='conn-card-info'>{file_svg} &nbsp;File: {conn.get('source_filename') or conn.get('database', 'Local File')}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='conn-card-info'>{loc_svg} &nbsp;Location: Local Storage</div>", unsafe_allow_html=True)
                    else:
                        globe_svg = get_icon("globe", size=14, color="#64748B")
                        user_svg = get_icon("user", size=14, color="#64748B")
                        st.markdown(f"<div class='conn-card-info'>{globe_svg} &nbsp;{conn.get('host', '127.0.0.1')}:{conn.get('port', 3306)}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='conn-card-info'>{user_svg} &nbsp;User: {conn.get('username', 'root')}</div>", unsafe_allow_html=True)
                    
                    # Card Footer
                    clock_svg = get_icon("clock", size=13, color="#64748B")
                    st.markdown(f"""
                    <div class='conn-card-footer'>
                        <span>{clock_svg} &nbsp;{relative_time}</span>
                        <span class='conn-usage-badge'>{conn.get("usage_count", 1)} connects</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                    # Interactive Action Buttons row directly inside native card container
                    st.markdown("<div class='conn-card-spacing'></div>", unsafe_allow_html=True)
                    btn_col1, btn_col2 = st.columns([5, 3])
                    with btn_col1:
                        # Primary action: Connect Again
                        if st.button("Connect", key=f"btn_reconn_{conn['id']}", use_container_width=True, type="primary"):
                            if db_type == "sqlite":
                                with st.spinner("Connecting to SQLite file..."):
                                    success, msg = reconnect_database(conn, "")
                                if success:
                                    st.session_state["menu"] = "Dashboard"
                                    st.query_params["page"] = "Dashboard"
                                    st.rerun()
                                else:
                                    st.error(f"Connection Failed: {msg}")
                            else:
                                st.session_state["reconnect_conn"] = conn
                                st.rerun()
                    with btn_col2:
                        # Delete stored card metadata
                        st.markdown(f'<div class="delete-button-marker" id="del-{conn["id"]}"></div>', unsafe_allow_html=True)
                        if st.button("Delete", key=f"btn_del_{conn['id']}", use_container_width=True, help="Remove connection details"):
                            delete_saved_connection(conn["id"])
                            st.toast(f"🗑️ Removed connection: {conn['database']}")
                            st.rerun()
                        
                st.markdown("<div class='conn-button-spacing'></div>", unsafe_allow_html=True)

    # ── Check & Trigger Reconnect Popup modal ──
    if "reconnect_conn" in st.session_state:
        reconnect_target = st.session_state.pop("reconnect_conn")
        if reconnect_target.get("database_type", "").lower() == "sqlite":
            with st.spinner("Connecting to SQLite file..."):
                success, msg = reconnect_database(reconnect_target, "")
            if success:
                st.success("Connected successfully!")
                st.toast("🚀 Database loaded! Redirecting to Dashboard...")
                st.session_state["menu"] = "Dashboard"
                st.query_params["page"] = "Dashboard"
                st.rerun()
            else:
                st.error(f"Connection Failed: {msg}")
        else:
            render_reconnect_modal(reconnect_target)

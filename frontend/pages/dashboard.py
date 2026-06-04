"""
Dashboard — DataPilot AI
Production-grade AI database analytics workspace with ChatGPT-style streaming.

Progressive rendering order (as each stage completes):
  1. SQL Preview         — appears the moment AI generates SQL  (~2-4s)
  2. Results Table       — appears the moment DB executes       (~50ms after SQL)
  3. Explanation         — updates SQL preview in-place         (~3-5s after SQL)
  4. Insight Cards       — appear when AI analysis completes    (~parallel)
  5. Chart               — appears with full insight context    (~parallel)
  6. Export Buttons      — appear after chart
"""
import time
import streamlit as st
from datetime import datetime

from components.sidebar import render_sidebar
from components.db_connection import render_db_connection
from components.query_input import render_query_input
from components.result_table import render_result_table
from components.chart_renderer import render_chart
from components.sql_preview import render_sql_preview
from components.export_buttons import render_export_buttons
from components.notification import show_success, show_error
from components.upload_database_box import render_upload_database_box
from components.disconnect_button import render_disconnect_button
from components.schema_viewer import render_schema_viewer
from components.metrics_cards import render_metrics_cards
from services.api_client import generate_sql, stream_analyze, optimize_query, generate_report
from utils.db_context import load_database_context
from utils.db_helpers import is_valid_db_info
from utils.icons import get_icon


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
_DASH_CSS = """
<style>
/* ── Main Block Overrides ── */
div.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
@media (max-width: 768px) {
    div.block-container {
        padding-top: 1rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 1.25rem !important;
        padding-right: 1.25rem !important;
    }
}
@media (max-width: 480px) {
    div.block-container {
        padding-top: 0.75rem !important;
        padding-bottom: 1.25rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
}

/* ── Header ── */
.dash-header-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    padding: 6px 0;
    margin-bottom: 4px;
    width: 100%;
}
.dash-header { flex-grow: 1; }
.dash-title { font-size: 1.6rem; font-weight: 800; color: #F8FAFC; line-height: 1.2; margin: 0; }
.dash-subtitle { font-size: 0.8rem; color: #64748B; margin-top: 2px; }

/* ── DB status pill ── */
.db-status-pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.2);
    border-radius: 20px; padding: 4px 10px;
    font-size: 0.76rem; font-weight: 600; color: #10B981;
    white-space: nowrap;
}

/* ── Divider ── */
.section-divider { border: none; border-top: 1px solid #1E293B; margin: 6px 0; }

/* ── Tabs ── */
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 8px; background: rgba(15,23,42,0.6); border-radius: 12px;
    padding: 6px; border: 1px solid #1E293B;
}
div[data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 8px; padding: 8px 20px; font-weight: 600;
    font-size: 0.9rem; color: #64748B; background: transparent;
}
div[data-testid="stTabs"] [aria-selected="true"] {
    background: linear-gradient(135deg, #6366F1, #8B5CF6) !important;
    color: white !important; box-shadow: 0 4px 12px rgba(99,102,241,0.35);
}

/* ── Results wrapper ── */
.results-wrapper {
    background: linear-gradient(135deg, rgba(15,23,42,0.8), rgba(11,17,32,0.8));
    border: 1px solid rgba(51,65,85,0.5); border-radius: 16px;
    padding: 18px 20px; margin-top: 12px;
}

/* ── Notice strip ── */
.notice-strip {
    background: rgba(245,158,11,0.07); border: 1px solid rgba(245,158,11,0.22);
    border-radius: 8px; padding: 8px 14px;
    font-size: 0.8rem; color: #FBBF24; margin-bottom: 10px;
}

/* ── Performance badges ── */
.perf-badge-row { display:flex; gap:8px; flex-wrap:wrap; margin:6px 0 10px 0; align-items:center; }
.perf-badge { display:inline-flex; align-items:center; gap:4px; border-radius:6px; padding:2px 8px; font-size:0.72rem; font-weight:700; }
.badge-easy   { background:rgba(16,185,129,0.12); color:#10B981; border:1px solid rgba(16,185,129,0.25); }
.badge-medium { background:rgba(245,158,11,0.12); color:#F59E0B; border:1px solid rgba(245,158,11,0.25); }
.badge-hard   { background:rgba(239,68,68,0.12);  color:#EF4444; border:1px solid rgba(239,68,68,0.25); }
.badge-cache  { background:rgba(99,102,241,0.12); color:#818CF8; border:1px solid rgba(99,102,241,0.25); }
.badge-time   { background:rgba(51,65,85,0.5);    color:#94A3B8; border:1px solid rgba(51,65,85,0.5); }

/* ── Streaming status bar ── */
.stream-stage {
    background: linear-gradient(135deg, rgba(15,23,42,0.95), rgba(11,17,32,0.95));
    border: 1px solid rgba(99,102,241,0.22); border-radius: 12px;
    padding: 12px 16px; margin: 8px 0;
    display: flex; align-items: center; gap: 12px;
    font-size: 0.86rem; color: #CBD5E1;
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
}
.stream-spinner {
    width: 16px; height: 16px; border-radius: 50%; flex-shrink: 0;
    border: 2px solid rgba(99,102,241,0.25); border-top-color: #6366F1;
    animation: dp-spin 0.75s linear infinite;
}
@keyframes dp-spin { to { transform: rotate(360deg); } }
.stream-icon { font-size: 1.1rem; }
.stream-msg  { flex: 1; line-height: 1.4; }

/* ── Stage done chips ── */
.stage-chip {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.2);
    border-radius: 20px; padding: 3px 10px;
    font-size: 0.72rem; font-weight: 600; color: #34D399;
    margin: 0 4px 4px 0;
}

/* ── Divider between sections ── */
.section-sep { border: none; border-top: 1px solid #1E293B; margin: 14px 0; }

/* ── Hide Streamlit's bottom "Running…" spinner — loading shown in button ── */
[data-testid="stStatusWidget"] { display: none !important; }
header [data-testid="stToolbar"] { display: none !important; }

/* ── Premium AI Actions ── */
.premium-actions-bar {
    display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
    margin: 16px 0 8px 0; padding: 12px 16px;
    background: linear-gradient(135deg, rgba(15,23,42,0.7), rgba(11,17,32,0.7));
    border: 1px solid rgba(99,102,241,0.2); border-radius: 12px;
}
.premium-actions-label {
    font-size: 0.72rem; font-weight: 700; color: #64748B;
    letter-spacing: 0.08em; text-transform: uppercase; white-space: nowrap;
}
.premium-result-marker {
    display: none !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.premium-result-marker) {
    background: linear-gradient(135deg, rgba(15,23,42,0.95), rgba(11,17,32,0.95)) !important;
    border: 1px solid rgba(99,102,241,0.3) !important;
    border-radius: 14px !important;
    padding: 20px 24px !important;
    margin-top: 12px !important;
}
.premium-result-title {
    font-size: 1rem; font-weight: 700; color: #A5B4FC; margin-bottom: 12px;
    display: flex; align-items: center; gap: 8px;
}

/* ── Responsive Dashboard ── */
@media (max-width: 768px) {
    .dash-header-container {
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
        padding: 4px 0;
    }
    .dash-title { font-size: 1.3rem !important; }
    .dash-subtitle { font-size: 0.74rem !important; }
    .db-status-pill { font-size: 0.72rem !important; padding: 3px 8px !important; }
    .section-divider { margin: 4px 0 !important; }
    .section-sep { margin: 8px 0 !important; }
    .results-wrapper { padding: 12px 10px !important; border-radius: 12px !important; }
    .perf-badge-row { gap: 4px !important; }
    .perf-badge { font-size: 0.65rem !important; padding: 2px 6px !important; }
    .stream-stage { padding: 8px 10px !important; font-size: 0.78rem !important; border-radius: 10px !important; }
    .notice-strip { font-size: 0.73rem !important; padding: 6px 10px !important; }
    .premium-actions-bar { padding: 8px 10px !important; gap: 6px !important; }
    .premium-actions-label { font-size: 0.65rem !important; }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.premium-result-marker) {
        padding: 12px 10px !important;
    }
    .premium-result-title { font-size: 0.88rem !important; }
    
    /* Segmented control tabs for mobile */
    div[data-testid="stTabs"] {
        margin-top: 0px !important;
        margin-bottom: 0px !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        padding: 4px !important;
        border-radius: 8px !important;
        gap: 2px !important;
        display: flex !important;
        width: 100% !important;
        justify-content: space-between !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"] {
        padding: 6px 4px !important;
        font-size: 0.76rem !important;
        flex: 1 1 50% !important;
        max-width: 50% !important;
        text-align: center !important;
        justify-content: center !important;
        border-radius: 6px !important;
    }

    /* Compact Mobile File Uploader */
    div[data-testid="stFileUploaderDropzone"] section > div > span {
        display: none !important;
    }
    div[data-testid="stFileUploaderDropzone"] section svg {
        display: none !important;
    }
    div[data-testid="stFileUploaderDropzone"] {
        padding: 8px 12px !important;
        min-height: unset !important;
        height: auto !important;
        background: rgba(30, 41, 59, 0.25) !important;
        border: 1px dashed rgba(99, 102, 241, 0.3) !important;
        border-radius: 10px !important;
    }
    div[data-testid="stFileUploaderDropzone"] section {
        padding: 4px 0 !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        gap: 4px !important;
    }
    div[data-testid="stFileUploaderDropzone"] span, 
    div[data-testid="stFileUploaderDropzone"] p, 
    div[data-testid="stFileUploaderDropzone"] small,
    div[data-testid="stFileUploaderDropzone"] label,
    div[data-testid="stFileUploaderDropzone"] section > div {
        font-size: 0.75rem !important;
        line-height: 1.2 !important;
    }
    div[data-testid="stFileUploaderDropzone"] span[data-testid="stWidgetLabel"] + div,
    div[data-testid="stFileUploaderDropzone"] section > div > small,
    div[data-testid="stFileUploaderDropzone"] section > div > span:last-child {
        font-size: 0.65rem !important;
        opacity: 0.7 !important;
    }
    div[data-testid="stFileUploaderDropzone"] button {
        margin: 4px auto !important;
        height: 32px !important;
        min-height: 32px !important;
        padding: 0 16px !important;
        border-radius: 6px !important;
        width: 100% !important;
    }
    div[data-testid="stFileUploaderDropzone"] button * {
        font-size: 0.75rem !important;
    }
}
@media (max-width: 480px) {
    .dash-header-container {
        gap: 6px;
        padding: 2px 0;
    }
    .dash-title { font-size: 1.15rem !important; }
    .dash-subtitle { font-size: 0.7rem !important; }
    .db-status-pill { font-size: 0.68rem !important; padding: 2px 6px !important; }
    .results-wrapper { padding: 8px 6px !important; margin-top: 8px !important; }
    .perf-badge-row { margin: 4px 0 6px 0 !important; }
    .perf-badge { font-size: 0.62rem !important; padding: 1px 4px !important; }
    .stream-stage { padding: 6px 8px !important; font-size: 0.74rem !important; border-radius: 8px !important; }
    .notice-strip { font-size: 0.7rem !important; padding: 4px 8px !important; }
    .premium-actions-bar { padding: 6px 8px !important; gap: 4px !important; margin: 8px 0 4px 0 !important; }
    .premium-actions-label { font-size: 0.6rem !important; }
    .premium-result-title { font-size: 0.78rem !important; margin-bottom: 8px !important; }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.premium-result-marker) {
        padding: 10px 8px !important;
        margin-top: 8px !important;
    }
    
    /* Segmented control tabs for micro viewports */
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        padding: 3px !important;
        border-radius: 6px !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"] {
        padding: 5px 2px !important;
        font-size: 0.72rem !important;
        border-radius: 4px !important;
    }

    /* Micro viewports file uploader dropzone spacing */
    div[data-testid="stFileUploaderDropzone"] {
        padding: 6px 8px !important;
        border-radius: 8px !important;
    }
    div[data-testid="stFileUploaderDropzone"] span, 
    div[data-testid="stFileUploaderDropzone"] p, 
    div[data-testid="stFileUploaderDropzone"] small,
    div[data-testid="stFileUploaderDropzone"] label,
    div[data-testid="stFileUploaderDropzone"] section > div {
        font-size: 0.7rem !important;
    }
    div[data-testid="stFileUploaderDropzone"] span[data-testid="stWidgetLabel"] + div,
    div[data-testid="stFileUploaderDropzone"] section > div > small,
    div[data-testid="stFileUploaderDropzone"] section > div > span:last-child {
        font-size: 0.6rem !important;
    }
    div[data-testid="stFileUploaderDropzone"] button {
        height: 28px !important;
        min-height: 28px !important;
    }
    div[data-testid="stFileUploaderDropzone"] button * {
        font-size: 0.7rem !important;
    }
}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Stage icon map
# ─────────────────────────────────────────────────────────────────────────────
_STAGE_ICONS = {
    "classifying":    "🧠",
    "generating_sql": "⚡",
    "executing":      "🗃️",
    "analyzing":      "🤖",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _save_to_history(user_query: str, generated_sql: str, result: dict | None = None) -> None:
    history: list = st.session_state.get("query_history", [])
    history = [h for h in history if h.get("query", "").strip().lower() != user_query.strip().lower()]
    from components.sidebar import _smart_title
    db_info = st.session_state.get("db_info", {})
    history.append({
        "query":         user_query,
        "sql":           generated_sql,
        "title":         _smart_title(user_query),
        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "result":        result,
        "database_name": db_info.get("database", ""),
    })
    st.session_state["query_history"] = history


def _show_stream_status(placeholder, message: str, stage: str = "") -> None:
    """Render the animated streaming status bar. The status message is the primary live indicator."""
    # Escape single quotes so they don't break the JS string literal
    safe_msg = message.replace("'", "\\'")
    placeholder.markdown(
        f"<script>"
        f"(function(){{try{{var d=window.parent.document;"
        f"var b=Array.from(d.querySelectorAll('button')).find(function(x){{return x.disabled&&x.textContent.includes('\u23f3');}});"
        f"if(b){{b.childNodes.forEach(function(n){{if(n.nodeType===3)n.textContent='\u23f3 {safe_msg}';}});}}"
        f"}}catch(e){{}}}})();"
        f"</script>",
        unsafe_allow_html=True,
    )


def _render_performance_badges(result: dict) -> None:
    cache_hit  = result.get("cache_hit", False)
    timing     = result.get("timing", {})
    total_ms   = timing.get("total_ms", 0)
    html = "<div class='perf-badge-row'>"
    if cache_hit:
        html += "<span class='perf-badge badge-cache'>⚡ CACHE HIT</span>"
    if total_ms:
        html += f"<span class='perf-badge badge-time'>⏱ {total_ms/1000:.1f}s total</span>"
        if timing.get("sql_gen_ms"):
            html += f"<span class='perf-badge badge-time'>SQL {timing['sql_gen_ms']/1000:.1f}s</span>"
        if timing.get("sql_exec_ms"):
            html += f"<span class='perf-badge badge-time'>DB {timing['sql_exec_ms']/1000:.2f}s</span>"
        if timing.get("parallel_ms"):
            html += f"<span class='perf-badge badge-time'>AI {timing['parallel_ms']/1000:.1f}s</span>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _typewriter_stream(placeholder, text: str, speed: float = 0.012) -> None:
    """
    Stream *text* word-by-word into *placeholder* with a typewriter effect.
    Uses Streamlit markdown so the output is nicely formatted.
    speed: seconds of delay between words (default ≈12 ms → ~80 words/sec).
    """
    import time
    words = text.split()
    displayed = ""
    for i, word in enumerate(words):
        displayed += (" " if i else "") + word
        placeholder.markdown(
            f"<div class='sql-explanation-box'>{displayed}▌</div>",
            unsafe_allow_html=True,
        )
        time.sleep(speed)
    # Final render without cursor
    placeholder.markdown(
        f"<div class='sql-explanation-box'>{displayed}</div>",
        unsafe_allow_html=True,
    )


def _update_history_item(user_query: str, result: dict) -> None:
    """Helper to update a cached query result inside the sidebar history."""
    history = st.session_state.get("query_history", [])
    for item in history:
        if item.get("query", "").strip().lower() == user_query.strip().lower():
            item["result"] = result
            break
    st.session_state["query_history"] = history


def _make_pdf_filename(user_query: str) -> str:
    """
    Derive a short, filesystem-safe PDF filename from the user's natural-language
    query.  Strategy (senior-dev thinking):
      1. Strip SQL keywords and common filler words so only domain nouns remain.
      2. Lowercase + keep only alphanumeric + spaces.
      3. Take up to the first 6 meaningful words.
      4. Join with underscores, append a compact timestamp.
    Examples:
      "Show top 10 movies by rating"  -> "top_movies_rating_20240528_2215.pdf"
      "Total revenue per region last year" -> "revenue_region_last_year_20240528_2215.pdf"
    """
    import re as _re
    from datetime import datetime as _dt

    # Words to strip (SQL keywords + generic filler)
    STOPWORDS = {
        "select", "show", "get", "find", "list", "give", "display", "fetch",
        "what", "which", "how", "many", "much", "the", "a", "an", "of", "in",
        "on", "for", "by", "to", "and", "or", "is", "are", "was", "were",
        "all", "me", "my", "i", "with", "from", "where", "having", "order",
        "group", "limit", "distinct", "count", "sum", "avg", "max", "min",
        "number", "total", "report", "data", "result", "results", "records",
        "using", "that", "this", "each", "per", "based",
    }

    # Lowercase, keep only letters/numbers/spaces
    clean = _re.sub(r"[^a-z0-9 ]", " ", user_query.lower())
    words = [w for w in clean.split() if w and w not in STOPWORDS]

    # Take up to 3 meaningful words
    slug = "_".join(words[:3]) or "report"

    # Compact timestamp: YYYYMMDD_HHMM
    ts = _dt.now().strftime("%Y%m%d_%H%M")

    return f"{slug}_{ts}.pdf"


def _render_premium_ai_actions(result: dict, user_query: str, do_optimize: bool = False, do_report: bool = False) -> None:
    """Render on-demand premium AI results below the main analytics panel."""
    sql         = result.get("sql", "")
    columns     = [c if isinstance(c, str) else str(c) for c in (result.get("columns") or result.get("data") and [k for k in result["data"][0].keys()] if result.get("data") else [])]
    rows        = result.get("data") or result.get("rows") or []
    explanation = result.get("explanation", "")

    if not sql:
        return

    db_info = st.session_state.get("db_info", {})
    dialect = db_info.get("database_type", db_info.get("db_type", "sqlite"))

    active_tab = result.get("active_premium_tab")

    # Update active tab state upon click
    if do_optimize:
        active_tab = "optimize"
        result["active_premium_tab"] = "optimize"
        st.session_state["last_result"] = result
        _update_history_item(user_query, result)
    elif do_report:
        active_tab = "report"
        result["active_premium_tab"] = "report"
        st.session_state["last_result"] = result
        _update_history_item(user_query, result)

    if not active_tab:
        return

    # Render Optimize Query results
    if active_tab == "optimize":
        opt_result = result.get("opt_result")
        if not opt_result:
            with st.spinner("Analyzing SQL with AI tool deep reasoning…"):
                opt_result = optimize_query(
                    sql=sql,
                    user_query=user_query,
                    dialect=dialect,
                )
                if opt_result.get("success"):
                    result["opt_result"] = opt_result
                    st.session_state["last_result"] = result
                    _update_history_item(user_query, result)

        if opt_result:
            if opt_result.get("success"):
                with st.container(border=True):
                    st.markdown("<div class='premium-result-marker'></div>", unsafe_allow_html=True)
                    st.markdown("<div class='premium-result-title'>Query Optimization Report</div>", unsafe_allow_html=True)

                    opt_sql = opt_result.get("optimized_sql", "")
                    if opt_sql and opt_sql.strip() != sql.strip():
                        st.code(opt_sql, language="sql")
                    else:
                        st.success("Your SQL is already well-optimized for this query.")
            else:
                err = opt_result.get("error", "Optimization failed.")
                st.error(err)

    # Render Business Report results
    elif active_tab == "report":
        report_result = result.get("report_result")
        if not report_result:
            with st.spinner("Generating business report with AI tool…"):
                report_result = generate_report(
                    sql=sql,
                    user_query=user_query,
                    columns=columns,
                    rows=rows[:50],   # send up to 50 rows for context
                    explanation=explanation,
                )
                if report_result.get("success"):
                    result["report_result"] = report_result
                    st.session_state["last_result"] = result
                    _update_history_item(user_query, result)

        if report_result:
            if report_result.get("success"):
                with st.container(border=True):
                    st.markdown("<div class='premium-result-marker'></div>", unsafe_allow_html=True)
                    st.markdown("<div class='premium-result-title'>Business Intelligence Report</div>", unsafe_allow_html=True)

                    exec_summary = report_result.get("executive_summary", "")
                    if exec_summary:
                        st.info(f"**Executive Summary:** {exec_summary}")

                    full_report = report_result.get("report_markdown", "")
                    if full_report:
                        st.markdown(full_report)

                    if full_report:
                        from utils.pdf_generator import convert_markdown_to_pdf
                        try:
                            pdf_bytes = convert_markdown_to_pdf(full_report)
                            st.download_button(
                                label="Download Report (PDF)",
                                data=pdf_bytes,
                                file_name=_make_pdf_filename(user_query),
                                mime="application/pdf",
                                key="btn_download_report",
                            )
                        except Exception as ex:
                            st.error(f"Failed to generate PDF: {ex}")
            else:
                err = report_result.get("error", "Report generation failed.")
                st.error(err)


def _render_skeletons(table_ph, chart_ph):
    """Render beautiful shimmering skeleton loaders for the table and chart."""
    skeleton_css = """
    <style>
    @keyframes skeleton-pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1.0; }
        100% { opacity: 0.6; }
    }
    .skeleton-box {
        background-color: rgba(99, 102, 241, 0.05);
        border: 1px solid rgba(99, 102, 241, 0.12);
        border-radius: 12px;
        animation: skeleton-pulse 1.8s ease-in-out infinite;
    }
    .skeleton-table {
        height: 200px;
        width: 100%;
        margin-bottom: 20px;
        display: flex;
        flex-direction: column;
        justify-content: space-evenly;
        padding: 16px;
    }
    .skeleton-line {
        height: 12px;
        background-color: rgba(99, 102, 241, 0.08);
        border-radius: 6px;
        width: 100%;
    }
    .skeleton-line.header {
        height: 18px;
        background-color: rgba(99, 102, 241, 0.16);
        width: 60%;
    }
    .skeleton-chart {
        height: 300px;
        width: 100%;
        display: flex;
        align-items: flex-end;
        justify-content: space-evenly;
        padding: 24px;
        margin-top: 15px;
    }
    .skeleton-bar {
        width: 8%;
        background-color: rgba(139, 92, 246, 0.1);
        border-radius: 6px 6px 0 0;
    }
    </style>
    """
    st.markdown(skeleton_css, unsafe_allow_html=True)
    
    with table_ph.container():
        st.markdown("""
        <div class="skeleton-box skeleton-table">
            <div class="skeleton-line header"></div>
            <div class="skeleton-line"></div>
            <div class="skeleton-line" style="width: 85%;"></div>
            <div class="skeleton-line" style="width: 90%;"></div>
            <div class="skeleton-line" style="width: 75%;"></div>
        </div>
        """, unsafe_allow_html=True)
        
    with chart_ph.container():
        st.markdown("""
        <div class="skeleton-box skeleton-chart">
            <div class="skeleton-bar" style="height: 40%;"></div>
            <div class="skeleton-bar" style="height: 65%;"></div>
            <div class="skeleton-bar" style="height: 50%;"></div>
            <div class="skeleton-bar" style="height: 85%;"></div>
            <div class="skeleton-bar" style="height: 30%;"></div>
            <div class="skeleton-bar" style="height: 70%;"></div>
            <div class="skeleton-bar" style="height: 95%;"></div>
            <div class="skeleton-bar" style="height: 55%;"></div>
        </div>
        """, unsafe_allow_html=True)


def _render_results(result: dict, user_query: str, placeholders: dict) -> None:
    """Static full render — used after rerun to restore session state into the layout placeholders."""
    from utils.settings_manager import get_setting
    intent = result.get("intent", "Database Query")

    if intent == "Conversation":
        with placeholders["explanation"].container():
            st.markdown(f"""
            <div class='sql-preview-card'>
                <div class='sql-preview-header'>
                    <span class='sql-preview-label'>AI Insights</span>
                </div>
                <div style='font-size:0.95rem; line-height:1.6; color:#E2E8F0; padding:10px 0;'>
                    {result.get("conversational_response", "")}
                </div>
            </div>
            """, unsafe_allow_html=True)
        return

    if intent == "Ambiguous":
        with placeholders["explanation"].container():
            st.markdown(f"""
            <div class='sql-preview-card'>
                <div class='sql-preview-header'>
                    <span class='sql-preview-label'>Clarify your request</span>
                </div>
                <div style='font-size:0.92rem; color:#94A3B8; margin-bottom:12px;'>
                    It looks like your request was a bit ambiguous. Did you mean one of these?
                </div>
            </div>
            """, unsafe_allow_html=True)
            suggestions = result.get("ambiguities", [])
            for idx, sug in enumerate(suggestions):
                if st.button(sug, key=f"ambig_sug_restored_{idx}_{sug[:15]}", use_container_width=True):
                    st.session_state["current_query"] = sug
                    st.session_state["_fill_text_after_suggestion"] = sug
                    st.rerun()
        return

    sql         = result.get("sql", "")
    explanation = result.get("explanation", "")
    data        = result.get("data", [])
    exp_mode = get_setting("explanation_mode")
    if exp_mode == "None":
        explanation = ""
    raw_chart = get_setting("chart_preference")
    chart_preference = "Auto" if "Auto" in raw_chart else raw_chart.replace(" Chart", "").replace(" Plot", "").lower()
    rec_chart = chart_preference if chart_preference != "Auto" else result.get("recommended_chart")
    
    with placeholders["perf"].container():
        _render_performance_badges(result)
        all_notices = (result.get("ambiguities") or []) + (result.get("warnings") or [])
        if all_notices:
            st.markdown(
                f"<div class='notice-strip'>⚠ {'  ·  '.join(str(n) for n in all_notices[:4])}</div>",
                unsafe_allow_html=True,
            )
            
    with placeholders["sql"].container():
        render_sql_preview(sql, explanation)
        
    with placeholders["table"].container():
        st.markdown("<div class='results-wrapper'>", unsafe_allow_html=True)
        render_result_table(data)
        
    with placeholders["chart"].container():
        st.markdown("<hr class='section-sep'>", unsafe_allow_html=True)
        render_chart(
            data,
            recommended_chart=rec_chart,
            chart_justification=result.get("chart_justification", ""),
            confidence_score=result.get("confidence_score"),
            confidence_label=result.get("confidence_label"),
            user_query=user_query,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        
    with placeholders["export"].container():
        st.markdown("<div style='margin-top:10px;'>", unsafe_allow_html=True)
        import pandas as pd
        df = pd.DataFrame(data)
        csv = df.to_csv(index=False).encode("utf-8")
        
        col_csv, col_opt, col_rpt, col_space = st.columns([2, 2.5, 2.5, 5])
        with col_csv:
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="query_results.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_opt:
            do_optimize = st.button(
                "Optimize Query",
                key="btn_optimize_query",
                help="Deep SQL analysis with AI tool",
                use_container_width=True,
            )
        with col_rpt:
            do_report = st.button(
                "Business Report",
                key="btn_business_report",
                help="Generate a professional business report with AI tool",
                use_container_width=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # Premium AI actions
    _render_premium_ai_actions(result, user_query, do_optimize, do_report)


# ─────────────────────────────────────────────────────────────────────────────
# Streaming pipeline — ChatGPT-style progressive disclosure
# ─────────────────────────────────────────────────────────────────────────────
def _run_streaming_query(user_query: str, db_info: dict, placeholders: dict) -> None:
    """
    Consume the SSE /query/stream-analyze endpoint and update Streamlit
    placeholders in real-time as each pipeline stage completes.
    """
    from components.result_table import render_result_table
    from components.chart_renderer import render_chart
    from components.sql_preview import render_sql_preview
    from components.export_buttons import render_export_buttons
    from services.api_client import stream_analyze

    # ── Use existing placeholders from display order ──────────────────────────
    status_ph      = placeholders["status"]
    perf_ph        = placeholders["perf"]
    sql_ph         = placeholders["sql"]
    explanation_ph = placeholders["explanation"]
    table_ph       = placeholders["table"]
    chart_ph       = placeholders["chart"]
    export_ph      = placeholders["export"]

    # ── Accumulated state ─────────────────────────────────────────────
    sql = ""; columns = []; rows = []; explanation = ""
    recommended_chart = None; chart_justification = ""
    confidence_score = None; confidence_label = None
    complexity = ""; cache_hit = False; timing = {}
    had_error = False; exec_duration = 0.0
    intent = "Database Query"
    conversational_response = ""
    ambiguous_suggestions = []

    # FIX (Problems 1 & 3): partial result written to session_state
    # incrementally so a page-switch never loses already-loaded data.
    # Initialise with the user_query so history can be updated even on
    # partial completion.
    _partial_result: dict = {"user_query": user_query}

    def _persist_partial():
        """Write whatever we have so far to session_state."""
        st.session_state["last_result"] = {
            "user_query":          user_query,
            "sql":                 sql,
            "explanation":         explanation,
            "data":                rows,
            "recommended_chart":   recommended_chart,
            "chart_justification": chart_justification,
            "confidence_score":    confidence_score,
            "confidence_label":    confidence_label,
            "ambiguities":         ambiguous_suggestions,
            "warnings":            [],
            "execution_duration":  exec_duration,
            "complexity":          complexity,
            "cache_hit":           cache_hit,
            "timing":              timing,
            "intent":              intent,
            "conversational_response": conversational_response,
        }

    def redraw_ui():
        if sql:
            with sql_ph.container():


                render_sql_preview(sql)

        if rows:
            with table_ph.container():
                render_result_table(rows)

            if recommended_chart:
                from utils.settings_manager import get_setting
                raw_chart = get_setting("chart_preference")
                pref = ("Auto" if "Auto" in raw_chart
                        else raw_chart.replace(" Chart", "").replace(" Plot", "").lower())
                final_chart = pref if pref != "Auto" else recommended_chart

                with chart_ph.container():
                    st.markdown("<hr class='section-sep'>", unsafe_allow_html=True)
                    render_chart(
                        rows,
                        recommended_chart=final_chart,
                        chart_justification=chart_justification,
                        confidence_score=confidence_score,
                        confidence_label=confidence_label,
                        user_query=user_query,
                    )

    st.session_state["last_result"] = None
    _show_stream_status(status_ph, "Classifying query complexity…", "classifying")

    try:
        for event_type, data in stream_analyze(user_query, db_info):

            if event_type == "stage_update":
                if data.get("complexity"):
                    complexity = data["complexity"]
                _show_stream_status(
                    status_ph, data.get("message", "…"), data.get("stage", "")
                )

            elif event_type == "intent_conversation":
                intent = "Conversation"
                conversational_response = data.get("response", "")
                explanation = conversational_response
                sql = ""
                rows = []
                _persist_partial()
                with explanation_ph.container():
                    st.markdown(f"""
                    <div class='sql-preview-card'>
                        <div class='sql-preview-header'>
                            <span class='sql-preview-label'>AI Insights</span>
                        </div>
                        <div style='font-size:0.95rem; line-height:1.6; color:#E2E8F0; padding:10px 0;'>
                            {conversational_response}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            elif event_type == "intent_ambiguous":
                intent = "Ambiguous"
                ambiguous_suggestions = data.get("suggestions", [])
                sql = ""
                rows = []
                _persist_partial()
                with explanation_ph.container():
                    st.markdown(f"""
                    <div class='sql-preview-card'>
                        <div class='sql-preview-header'>
                            <span class='sql-preview-label'>Clarify your request</span>
                        </div>
                        <div style='font-size:0.92rem; color:#94A3B8; margin-bottom:12px;'>
                            It looks like your request was a bit ambiguous. Did you mean one of these?
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    for idx, sug in enumerate(ambiguous_suggestions):
                        if st.button(sug, key=f"ambig_sug_{idx}_{sug[:15]}", use_container_width=True):
                            st.session_state["current_query"] = sug
                            st.session_state["_fill_text_after_suggestion"] = sug
                            st.rerun()

            elif event_type == "sql_ready":
                sql = data.get("sql", "")
                cache_hit = data.get("cached", False)
                elapsed_s = data.get("elapsed_ms", 0) / 1000
                _show_stream_status(
                    status_ph,
                    f"✅ SQL ready ({elapsed_s:.1f}s) — executing query…",
                    "executing",
                )
                if sql:
                    with sql_ph.container():
                        render_sql_preview(sql)
                    # Persist SQL as soon as it arrives so a page-switch
                    # during DB execution doesn't lose it.
                    _persist_partial()

            elif event_type == "data_ready":
                columns       = data.get("columns", [])
                rows          = data.get("rows", [])
                exec_duration = data.get("execution_duration", 0.0)
                n = len(rows)
                _show_stream_status(
                    status_ph,
                    f"📊 {n:,} rows in {exec_duration * 1000:.0f}ms — generating AI explanation…",
                    "analyzing",
                )
                redraw_ui()
                # FIX (Problem 3): persist after data arrives — the most
                # important milestone. If the user navigates away now the
                # table is already saved and will be restored on return.
                _persist_partial()

            elif event_type == "chart_ready":
                recommended_chart   = data.get("recommended_chart", "table_only")
                chart_justification = data.get("chart_justification", "")
                redraw_ui()
                _persist_partial()

            elif event_type == "explanation_ready":
                explanation = data.get("explanation", "")
                if explanation:
                    _typewriter_stream(explanation_ph, explanation)
                # FIX (Problem 1): explanation now arrives in full because
                # the token budget was raised to 800 and the timeout to 25s
                # in explanation_service.py. Persist it immediately.
                _persist_partial()

            elif event_type == "insights_ready":
                pass

            elif event_type == "complete":
                recommended_chart   = data.get("recommended_chart", recommended_chart or "table_only")
                chart_justification = data.get("chart_justification", chart_justification)
                confidence_score    = data.get("confidence_score")
                confidence_label    = data.get("confidence_label")
                total_ms            = data.get("total_ms", 0)
                timing = {"total_ms": total_ms}

                status_ph.empty()

                with perf_ph.container():
                    _render_performance_badges({
                        "complexity": complexity,
                        "cache_hit": cache_hit,
                        "timing": timing,
                    })

                redraw_ui()

                with export_ph.container():
                    import pandas as pd
                    df = pd.DataFrame(rows)
                    csv = df.to_csv(index=False).encode("utf-8")
                    col_csv, col_opt, col_rpt, col_space = st.columns([2, 2.5, 2.5, 5])
                    with col_csv:
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name="query_results.csv",
                            mime="text/csv",
                            use_container_width=True,
                            key="btn_download_csv_stream",
                        )
                    with col_opt:
                        st.button(
                            "Optimize Query",
                            key="btn_optimize_query_stream",
                            help="Deep SQL analysis with AI tool",
                            use_container_width=True,
                            disabled=True,
                        )
                    with col_rpt:
                        st.button(
                            "Business Report",
                            key="btn_business_report_stream",
                            help="Generate a professional business report with AI tool",
                            use_container_width=True,
                            disabled=True,
                        )

            elif event_type == "error":
                had_error = True
                status_ph.empty()
                st.session_state["is_generating"] = False
                st.session_state["active_query"] = None
                err_sql = data.get("sql")
                if err_sql:
                    with sql_ph.container():
                        render_sql_preview(err_sql)
                    explanation_ph.markdown(
                        f"<div class='sql-explanation-box'>❌ {data.get('message', 'Execution failed.')}</div>",
                        unsafe_allow_html=True,
                    )
                st.error(f"❌ {data.get('message', 'Analysis failed.')}")
                break

    except Exception as exc:
        had_error = True
        status_ph.empty()
        st.session_state["is_generating"] = False
        st.session_state["active_query"] = None
        st.error(f"❌ Unexpected error during streaming: {exc}")

    # ── Final save and sidebar update ────────────────────────────────
    if not had_error and (sql or intent in ["Conversation", "Ambiguous"]):
        # Final persist with complete timing data.
        _persist_partial()
        st.session_state["should_scroll"] = True
        st.session_state["is_generating"] = False
        # Bug 1 fix: clear the active_query now that the result is fully saved
        st.session_state["active_query"] = None
        _save_to_history(user_query, sql, st.session_state["last_result"])
        try:
            from utils.settings_manager import log_activity
            log_activity(f"Executed query: \"{user_query}\"")
        except Exception:
            pass
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Main dashboard
# ─────────────────────────────────────────────────────────────────────────────
def show_dashboard():
    render_sidebar()
    st.markdown(_DASH_CSS, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────── #
    db_status_html = ""
    if st.session_state.get("connected"):
        db_info = st.session_state.get("db_info", {})
        db_type = db_info.get("database_type", db_info.get("db_type", "")).upper()
        db_status_html = f"<span class='db-status-pill'>🟢 Connected &bull; {db_type}</span>"

    st.markdown(f"""
    <div class='dash-header-container'>
        <div class='dash-header'>
            <div class='dash-title'>DataPilot AI</div>
            <div class='dash-subtitle'>AI-powered SQL analytics — results stream as they're ready.</div>
        </div>
        {db_status_html}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    # ── NOT CONNECTED ─────────────────────────────────────────────────── #
    if not st.session_state.get("connected"):
        st.markdown("<div style='max-width:720px; margin:0 auto;'>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Initialize Database", "Import Your Data"])
        with tab1:
            render_db_connection()
        with tab2:
            render_upload_database_box()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # ── Validate db_info ──────────────────────────────────────────────── #
    db_info = st.session_state.get("db_info", {})
    if not is_valid_db_info(db_info):
        st.error("Database connection is incomplete. Please reconnect.")
        render_disconnect_button()
        return

    # ── Load schema if needed ─────────────────────────────────────────── #
    if not st.session_state.get("schema_loaded"):
        with st.spinner("Loading database schema…"):
            ok, msg = load_database_context(db_info)
        if not ok:
            st.error(f"Could not load schema: {msg}")
            render_disconnect_button()
            return
        st.rerun()

    # ── Connected: header strip + KPIs ────────────────────────────────── #
    render_disconnect_button()
    render_metrics_cards()
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    # ── Two-column workspace: Query Input | Schema Explorer ───────────── #
    col_main, col_schema = st.columns([7, 3], gap="medium")

    with col_schema:
        render_schema_viewer()

    with col_main:
        if "query_error" in st.session_state:
            show_error(st.session_state.pop("query_error"))
        user_query = render_query_input()

    # ── Define global placeholders to ensure immediate clearing/skeletons ── #
    status_ph      = st.empty()   # animated status bar
    perf_ph        = st.empty()   # performance badges
    sql_ph         = st.empty()   # SQL code block
    explanation_ph = st.empty()   # AI explanation (typewriter streamed)
    table_ph       = st.empty()   # results table
    chart_ph       = st.empty()   # chart panel
    export_ph      = st.empty()   # export buttons

    placeholders = {
        "status": status_ph,
        "perf": perf_ph,
        "sql": sql_ph,
        "explanation": explanation_ph,
        "table": table_ph,
        "chart": chart_ph,
        "export": export_ph,
    }

    if user_query:
        st.session_state["last_result"] = None
        st.session_state["is_generating"] = True
        st.session_state["active_query"] = user_query
        
        # Explicitly empty all placeholders to remove previous run's components (dataframes, tab widgets, charts)
        status_ph.empty()
        perf_ph.empty()
        sql_ph.empty()
        explanation_ph.empty()
        table_ph.empty()
        chart_ph.empty()
        export_ph.empty()
        
        _render_skeletons(table_ph, chart_ph)
        _run_streaming_query(user_query, db_info, placeholders)
    elif st.session_state.get("is_generating") and st.session_state.get("active_query"):
        # User navigated away mid-stream and came back — re-run the stream
        
        # Explicitly empty all placeholders to remove previous run's components (dataframes, tab widgets, charts)
        status_ph.empty()
        perf_ph.empty()
        sql_ph.empty()
        explanation_ph.empty()
        table_ph.empty()
        chart_ph.empty()
        export_ph.empty()
        
        _render_skeletons(table_ph, chart_ph)
        resumed_query = st.session_state["active_query"]
        _run_streaming_query(resumed_query, db_info, placeholders)
    else:
        # Restore last result after sidebar click / export rerun.
        # FIX: Do not re-render the old result while a new query is in
        # flight. on_generate_click() clears last_result and sets
        # is_generating=True. On that first rerun user_query is None
        # (pending_query hasn't been popped yet), so without this guard
        # the old result would flash back on screen for one full cycle.
        if not st.session_state.get("is_generating"):
            last = st.session_state.get("last_result")
            if last:
                _render_results(last, last.get("user_query", ""), placeholders)

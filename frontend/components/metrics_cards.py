"""
Metrics Cards — DataPilot AI
Premium KPI card strip shown after database connection.
"""
import streamlit as st
from utils.schema_helpers import format_metric_number


_CSS = """
<style>
.kpi-strip {
    display: flex;
    gap: 8px;
    margin-bottom: 0px;
    flex-wrap: wrap;
}
.kpi-card {
    flex: 1;
    min-width: 120px;
    background: linear-gradient(135deg, rgba(15,23,42,0.9), rgba(11,17,32,0.9));
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 10px;
    padding: 8px 12px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s ease, transform 0.2s ease;
}
.kpi-card:hover {
    border-color: rgba(99,102,241,0.35);
    transform: translateY(-1px);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    border-radius: 10px 10px 0 0;
}
.kpi-card-blue::before  { background: linear-gradient(90deg, #6366F1, #8B5CF6); }
.kpi-card-green::before { background: linear-gradient(90deg, #10B981, #34D399); }
.kpi-card-amber::before { background: linear-gradient(90deg, #F59E0B, #FBBF24); }
.kpi-card-pink::before  { background: linear-gradient(90deg, #EC4899, #F472B6); }
.kpi-label {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #475569;
    margin-bottom: 2px;
}
.kpi-value {
    font-size: 1.2rem;
    font-weight: 800;
    color: #E2E8F0;
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
}
.kpi-sub {
    font-size: 0.62rem;
    color: #475569;
    margin-top: 1px;
}

/* ── Responsive KPI Cards ── */
@media (max-width: 768px) {
    .kpi-strip {
        gap: 6px !important;
    }
    .kpi-card {
        min-width: calc(50% - 4px) !important;
        flex: 1 1 calc(50% - 4px) !important;
        padding: 6px 10px !important;
    }
    .kpi-label { font-size: 0.6rem !important; }
    .kpi-value { font-size: 1rem !important; }
    .kpi-sub { font-size: 0.58rem !important; }
}
@media (max-width: 480px) {
    .kpi-card {
        padding: 6px 8px !important;
    }
    .kpi-value { font-size: 0.85rem !important; }
    .kpi-label { font-size: 0.58rem !important; }
    .kpi-sub { font-size: 0.55rem !important; }
}
@media (max-width: 375px) {
    .kpi-card {
        min-width: calc(50% - 3px) !important;
        padding: 5px 6px !important;
    }
    .kpi-value { font-size: 0.8rem !important; }
    .kpi-label { font-size: 0.55rem !important; }
}
</style>
"""


def render_metrics_cards():
    if not st.session_state.get("connected"):
        return

    db_stats = st.session_state.get("db_stats", {})
    total_rows  = db_stats.get("total_rows", 0)
    table_count = db_stats.get("table_count", 0)

    db_info = st.session_state.get("db_info", {})
    current_db = db_info.get("database", "")

    # Calculate queries run and average execution time for the active database connection on the fly
    db_queries = [
        item for item in st.session_state.get("query_history", [])
        if item.get("database_name") == current_db
    ]

    queries_today = len(db_queries)

    durations = []
    for item in db_queries:
        dur = item.get("execution_duration")
        if dur is None and item.get("result"):
            dur = item.get("result", {}).get("execution_duration")
        if dur is not None:
            durations.append(float(dur))

    if durations:
        avg_time = sum(durations) / len(durations)
    else:
        avg_time = 0.0

    cards = [
        {
            "color": "blue",
            "label": "Total Rows",
            "value": format_metric_number(total_rows),
            "sub": "across all tables",
        },
        {
            "color": "green",
            "label": "Tables",
            "value": str(table_count),
            "sub": "in active dataset",
        },
        {
            "color": "amber",
            "label": "Queries Run",
            "value": str(queries_today),
            "sub": "this session",
        },
        {
            "color": "pink",
            "label": "Avg Exec Time",
            "value": f"{avg_time:.2f}s",
            "sub": "per SQL query",
        },
    ]

    st.markdown(_CSS, unsafe_allow_html=True)

    cards_html = ""
    for c in cards:
        cards_html += f"""
        <div class='kpi-card kpi-card-{c["color"]}'>
            <div class='kpi-label'>{c["label"]}</div>
            <div class='kpi-value'>{c["value"]}</div>
            <div class='kpi-sub'>{c["sub"]}</div>
        </div>"""

    st.markdown(f"<div class='kpi-strip'>{cards_html}</div>", unsafe_allow_html=True)

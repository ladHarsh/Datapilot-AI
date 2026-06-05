"""
Premium Chart Renderer — DataPilot AI

Multi-chart visualization panel with:
  - AI-recommended chart shown first and auto-selected (marked ★)
  - All compatible chart types available as switchable tabs
  - 7 chart types: bar | line | area | pie | scatter | heatmap | histogram
  - AI insight cards, executive narrative, confidence badge
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ─────────────────────────────────────────────────────────────────────────────
# Dark-theme palette & layout defaults
# ─────────────────────────────────────────────────────────────────────────────
_PALETTE = [
    "#6366F1", "#8B5CF6", "#EC4899", "#14B8A6",
    "#F59E0B", "#10B981", "#3B82F6", "#EF4444",
    "#A78BFA", "#34D399",
]
_CHART_BG   = "rgba(0,0,0,0)"
_PAPER_BG   = "rgba(0,0,0,0)"
_GRID_COLOR = "rgba(51,65,85,0.5)"
_FONT_COLOR = "#CBD5E1"
_TITLE_COLOR = "#E2E8F0"

_BASE_LAYOUT = dict(
    paper_bgcolor=_PAPER_BG,
    plot_bgcolor=_CHART_BG,
    font=dict(color=_FONT_COLOR, family="Inter, sans-serif", size=11),
    margin=dict(t=40, l=45, r=20, b=65),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        borderwidth=0,
        font=dict(color=_FONT_COLOR, size=10),
        orientation="h",
        yanchor="top",
        y=-0.22,
        xanchor="center",
        x=0.5
    ),
    height=330,
)


def _apply_base(fig: go.Figure, title: str = "") -> go.Figure:
    layout = dict(**_BASE_LAYOUT)
    if title:
        layout["title"] = dict(text=title, font=dict(color=_TITLE_COLOR, size=14), x=0)
    fig.update_layout(**layout)
    fig.update_xaxes(gridcolor=_GRID_COLOR, zeroline=False, tickfont=dict(color=_FONT_COLOR))
    fig.update_yaxes(gridcolor=_GRID_COLOR, zeroline=False, tickfont=dict(color=_FONT_COLOR))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Score-based chart recommender  (replaces old keyword-only heuristic)
# ─────────────────────────────────────────────────────────────────────────────
_TIME_KW = {"date", "month", "year", "week", "day", "time", "period", "quarter", "hour", "timestamp"}


def _score_charts(df: pd.DataFrame, user_query: str = "") -> dict[str, int]:
    """Score every chart type 0-100 based on data shape + query signals.

    Higher = better fit.  The winner becomes the default (first) tab.
    """
    if df.empty or len(df.columns) < 1:
        return {}

    numeric_cols  = list(df.select_dtypes(include="number").columns)
    cat_cols      = [c for c in df.columns if c not in numeric_cols]
    n_rows        = len(df)
    n_cols        = len(df.columns)
    cols_lower    = [c.lower() for c in df.columns]
    q             = user_query.lower()

    # Data-shape flags
    has_time   = any(any(kw in c for kw in _TIME_KW) for c in cols_lower)
    n_num      = len(numeric_cols)
    n_cat      = len(cat_cols)
    single_num = (n_cols == 1 and n_num == 1)

    # Cardinality of the primary categorical column (if any)
    cat_cardinality = df[cat_cols[0]].nunique() if cat_cols else 0

    scores: dict[str, int] = {}

    # ── Bar Chart ────────────────────────────────────────────────────────────
    # Good for: categorical comparisons, rankings, aggregations
    if n_num >= 1:
        s = 40
        # Prefer bar when there is a clear categorical axis
        if n_cat >= 1:                                s += 15
        # Ranking / top-N signals
        if re.search(r"\b(top|rank|best|worst|highest|lowest|most|least|leading|bottom)\b", q):  s += 25
        # Comparison signal
        if re.search(r"\b(compare|comparison|vs|versus|between)\b", q):                         s += 20
        # Penalise heavily when a time axis is present (line is better)
        if has_time:                                  s -= 30
        # Penalise for very many rows (bar gets cluttered)
        if n_rows > 30:                               s -= 10
        scores["bar_chart"] = max(s, 0)

    # ── Line Chart ───────────────────────────────────────────────────────────
    # Good for: trends over time, sequential data
    if n_num >= 1 and (has_time or n_rows >= 4):
        s = 35
        # Strong: actual date/time column in results
        if has_time:                                  s += 40
        # Query trend signals
        if re.search(r"\b(trend|over\s+time|growth|increase|decrease|change|monthly|yearly|weekly|daily|quarter|annual|evolution)\b", q): s += 30
        # More rows → sequential data more likely
        if n_rows >= 12:                              s += 10
        if n_rows >= 30:                              s += 5
        # Multiple numeric series = nice multi-line chart
        if n_num > 1:                                 s += 8
        scores["line_chart"] = max(s, 0)

    # ── Area Chart ───────────────────────────────────────────────────────────
    # Similar to line but emphasises volume; score slightly below line
    if n_num >= 1 and (has_time or n_rows >= 4):
        s = scores.get("line_chart", 35) - 8   # area is second-choice to line
        if re.search(r"\b(area|volume|cumulative|total\s+over)\b", q): s += 20
        scores["area_chart"] = max(s, 0)

    # ── Pie / Donut Chart ────────────────────────────────────────────────────
    # Good for: proportions, shares, composition (few slices)
    if n_cat >= 1 and n_num >= 1:
        s = 30
        # Ideal slice count: 2-8
        if 2 <= cat_cardinality <= 8:                s += 25
        if cat_cardinality > 15:                     s -= 25   # too many slices
        # Query signals
        if re.search(r"\b(proportion|share|breakdown|percent|percentage|composition|split|contribution|pie|donut|ratio)\b", q): s += 35
        # Distribution of a small result set
        if n_rows <= 8 and n_cat >= 1:              s += 15
        # Penalise when time is present (pie doesn't show time)
        if has_time:                                 s -= 20
        scores["pie_chart"] = max(s, 0)

    # ── Scatter Plot ─────────────────────────────────────────────────────────
    # Good for: correlation between 2+ numeric columns
    if n_num >= 2:
        s = 25
        # Query signals
        if re.search(r"\b(correlation|scatter|relationship|vs|versus|between|impact|effect|influence)\b", q): s += 40
        if n_num >= 3:                               s += 10   # bubble-like bonus
        # More rows = more points = better scatter
        if n_rows >= 15:                             s += 10
        scores["scatter_plot"] = max(s, 0)

    # ── Heatmap ──────────────────────────────────────────────────────────────
    # Good for: 2-categorical × 1-numeric matrices, or correlation matrices
    if (n_cat >= 2 and n_num >= 1) or n_num >= 3:
        s = 20
        if n_cat >= 2 and n_num >= 1:                s += 20
        if re.search(r"\b(heatmap|matrix|by\s+\w+\s+and\s+\w+|cross|pivot)\b", q): s += 35
        if n_num >= 4:                               s += 10   # correlation matrix
        scores["heatmap"] = max(s, 0)

    # ── Histogram ────────────────────────────────────────────────────────────
    # Good for: distribution of a single numeric column
    if n_num >= 1:
        s = 15
        if single_num:                               s += 40   # exactly one numeric col
        if re.search(r"\b(distribution|spread|frequency|histogram|range|bucket|bin)\b", q): s += 35
        if n_rows >= 20:                             s += 10   # needs enough data
        scores["histogram"] = max(s, 0)

    return scores


def _heuristic_chart(df: pd.DataFrame, user_query: str = "") -> str:
    """Return the single best chart key for this DataFrame + query."""
    if df.empty or len(df.columns) < 1:
        return "table_only"
    scores = _score_charts(df, user_query)
    if not scores:
        return "table_only"
    best = max(scores, key=lambda k: scores[k])
    return best


# ─────────────────────────────────────────────────────────────────────────────
# Individual chart builders
# ─────────────────────────────────────────────────────────────────────────────
def _smart_x_y(df: pd.DataFrame):
    numeric = list(df.select_dtypes(include="number").columns)
    non_numeric = [c for c in df.columns if c not in numeric]
    x = non_numeric[0] if non_numeric else df.columns[0]
    y = numeric[0] if numeric else (df.columns[1] if len(df.columns) > 1 else df.columns[0])
    return x, y


def _bar(df: pd.DataFrame, user_query: str) -> go.Figure:
    x, y = _smart_x_y(df)
    numeric_cols = list(df.select_dtypes(include="number").columns)
    if len(numeric_cols) > 1:
        fig = px.bar(df, x=x, y=numeric_cols, barmode="group", color_discrete_sequence=_PALETTE)
    else:
        fig = px.bar(df, x=x, y=y, color_discrete_sequence=_PALETTE)
    fig.update_traces(marker_line_width=0)
    return _apply_base(fig, f"Comparison — {y}")


def _line(df: pd.DataFrame, user_query: str) -> go.Figure:
    x, y = _smart_x_y(df)
    numeric_cols = list(df.select_dtypes(include="number").columns)
    if len(numeric_cols) > 1:
        fig = px.line(df, x=x, y=numeric_cols, color_discrete_sequence=_PALETTE, markers=True)
    else:
        fig = px.line(df, x=x, y=y, color_discrete_sequence=_PALETTE, markers=True)
    fig.update_traces(line_width=2.5)
    return _apply_base(fig, f"Trend — {y}")


def _area(df: pd.DataFrame, user_query: str) -> go.Figure:
    x, y = _smart_x_y(df)
    numeric_cols = list(df.select_dtypes(include="number").columns)
    y_cols = numeric_cols if len(numeric_cols) > 1 else [y]
    fig = go.Figure()
    for i, col in enumerate(y_cols):
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(go.Scatter(
            x=df[x], y=df[col], mode="lines", name=col,
            fill="tozeroy",
            line=dict(color=color, width=2),
            fillcolor=color.replace(")", ", 0.15)").replace("rgb", "rgba"),
        ))
    return _apply_base(fig, f"Area — {y_cols[0]}")


def _pie(df: pd.DataFrame, user_query: str) -> go.Figure:
    x, y = _smart_x_y(df)
    fig = px.pie(df, names=x, values=y, color_discrete_sequence=_PALETTE, hole=0.35)
    fig.update_traces(textfont_color="#E2E8F0", marker=dict(line=dict(color="#0B1120", width=2)))
    return _apply_base(fig, f"Composition — {y}")


def _scatter(df: pd.DataFrame, user_query: str) -> go.Figure:
    numeric_cols = list(df.select_dtypes(include="number").columns)
    cat_cols = [c for c in df.columns if c not in numeric_cols]
    x = numeric_cols[0] if len(numeric_cols) >= 1 else df.columns[0]
    y = numeric_cols[1] if len(numeric_cols) >= 2 else (numeric_cols[0] if numeric_cols else df.columns[0])
    color_col = cat_cols[0] if cat_cols else None
    size_col = numeric_cols[2] if len(numeric_cols) >= 3 else None
    fig = px.scatter(df, x=x, y=y, color=color_col, size=size_col,
                     color_discrete_sequence=_PALETTE, opacity=0.8)
    fig.update_traces(marker=dict(line=dict(width=1, color="#0B1120")))
    return _apply_base(fig, f"Relationship — {x} vs {y}")


def _heatmap(df: pd.DataFrame, user_query: str) -> go.Figure:
    numeric_cols = list(df.select_dtypes(include="number").columns)
    cat_cols = [c for c in df.columns if c not in numeric_cols]
    if len(cat_cols) >= 2 and numeric_cols:
        pivot = df.pivot_table(values=numeric_cols[0], index=cat_cols[0],
                               columns=cat_cols[1], aggfunc="sum", fill_value=0)
        fig = px.imshow(pivot, color_continuous_scale="Viridis", aspect="auto")
        fig.update_coloraxes(colorbar_tickfont_color=_FONT_COLOR)
    elif len(numeric_cols) >= 2:
        corr = df[numeric_cols].corr()
        fig = px.imshow(corr, color_continuous_scale="RdBu_r", aspect="auto", zmin=-1, zmax=1)
    else:
        return _bar(df, user_query)
    return _apply_base(fig, "Heatmap")


def _histogram(df: pd.DataFrame, user_query: str) -> go.Figure:
    numeric_cols = list(df.select_dtypes(include="number").columns)
    col = numeric_cols[0] if numeric_cols else df.columns[0]
    fig = px.histogram(df, x=col, nbins=20, color_discrete_sequence=_PALETTE)
    fig.update_traces(marker_line_width=0.5, marker_line_color="#0B1120")
    return _apply_base(fig, f"Distribution — {col}")


# ─────────────────────────────────────────────────────────────────────────────
# Chart registry
# ─────────────────────────────────────────────────────────────────────────────
# Note: table_only is intentionally excluded — the Result Table section already shows raw data.
_ALL_CHART_TYPES: list[tuple[str, str]] = [
    ("bar_chart",    "Bar"),
    ("line_chart",   "Line"),
    ("area_chart",   "Area"),
    ("pie_chart",    "Pie"),
    ("scatter_plot", "Scatter"),
    ("heatmap",      "Heatmap"),
    ("histogram",    "Histogram"),
]

_BUILDER_MAP: dict[str, Any] = {
    "bar_chart":    _bar,
    "line_chart":   _line,
    "area_chart":   _area,
    "pie_chart":    _pie,
    "scatter_plot": _scatter,
    "heatmap":      _heatmap,
    "histogram":    _histogram,
    "table_only":   None,  # kept for alias fallback only
}

_CHART_ALIAS: dict[str, str] = {
    "bar": "bar_chart", "line": "line_chart", "area": "area_chart",
    "pie": "pie_chart", "scatter": "scatter_plot",
}


def _normalise_chart_key(raw: str | None) -> str | None:
    """Normalise a raw chart key string. Returns None if raw is empty/None."""
    if not raw:
        return None
    raw = raw.lower().strip()
    return _CHART_ALIAS.get(raw, raw)


def _resolve_best_chart(df: pd.DataFrame, recommended_chart: str | None, user_query: str, eligible: list) -> str:
    """Determine the best chart type using a priority chain:
    1. Explicit AI-recommended chart (if valid and eligible)
    2. Heuristic analysis of the DataFrame + query
    3. First chart in the eligible list as the final fallback
    """
    eligible_keys = [k for k, _ in eligible]

    # Priority 1: AI-recommended chart
    normalised = _normalise_chart_key(recommended_chart)
    if normalised and normalised != "table_only":
        if normalised in eligible_keys:
            return normalised
        # AI recommended a type that isn't naturally eligible — inject it anyway
        if normalised in _BUILDER_MAP and _BUILDER_MAP[normalised] is not None:
            return normalised

    # Priority 2: Heuristic
    heuristic = _heuristic_chart(df, user_query)
    if heuristic and heuristic != "table_only" and heuristic in eligible_keys:
        return heuristic

    # Priority 3: First eligible chart
    return eligible_keys[0] if eligible_keys else "bar_chart"


def _eligible_charts(df: pd.DataFrame, user_query: str = "") -> list[tuple[str, str]]:
    """Return (key, label) pairs for chart types that work for this DataFrame,
    ordered from most-relevant to least-relevant using the scoring system.
    table_only is intentionally excluded — raw data is in the Result Table section.
    """
    numeric_cols = df.select_dtypes(include="number").columns
    cat_cols = [c for c in df.columns if c not in numeric_cols]
    cols_lower = [c.lower() for c in df.columns]
    has_date = any(
        any(kw in c for kw in _TIME_KW)
        for c in cols_lower
    )

    # Build the set of charts that CAN render this data
    eligible_keys: set[str] = set()
    if len(numeric_cols) >= 1:
        eligible_keys.update(["bar_chart", "histogram"])
    if has_date or len(df) >= 3:
        eligible_keys.update(["line_chart", "area_chart"])
    if len(cat_cols) >= 1 and len(numeric_cols) >= 1 and len(df) <= 20:
        eligible_keys.add("pie_chart")
    if len(numeric_cols) >= 2:
        eligible_keys.add("scatter_plot")
    if (len(cat_cols) >= 2 and len(numeric_cols) >= 1) or len(numeric_cols) >= 3:
        eligible_keys.add("heatmap")

    # Score the eligible charts and sort by score descending
    scores = _score_charts(df, user_query)
    eligible_scored = [
        (key, label, scores.get(key, 0))
        for key, label in _ALL_CHART_TYPES
        if key in eligible_keys
    ]
    eligible_scored.sort(key=lambda x: x[2], reverse=True)

    result = [(key, label) for key, label, _ in eligible_scored]
    return result or [("bar_chart", "Bar")]


# ─────────────────────────────────────────────────────────────────────────────
# CSS blocks
# ─────────────────────────────────────────────────────────────────────────────
_INSIGHT_CSS = """
<style>
.ic { flex:1; min-width:200px; border-radius:10px; padding:12px 14px;
      background:rgba(15,23,42,0.7); border:1px solid rgba(51,65,85,0.6); }
.ic-trend    { border-left:3px solid #6366F1; }
.ic-positive { border-left:3px solid #10B981; }
.ic-negative { border-left:3px solid #EF4444; }
.ic-warning  { border-left:3px solid #F59E0B; }
.ic-neutral  { border-left:3px solid #6366F1; }
.ic-label { font-size:0.65rem; font-weight:700; text-transform:uppercase;
            letter-spacing:0.8px; color:#64748B; margin-bottom:4px; }
.ic-title { font-size:0.84rem; font-weight:700; color:#E2E8F0; margin-bottom:3px; }
.ic-body  { font-size:0.78rem; color:#94A3B8; line-height:1.45; }
.narrative-box {
  background:rgba(99,102,241,0.06); border:1px solid rgba(99,102,241,0.18);
  border-radius:10px; padding:14px 16px; margin-bottom:12px;
  font-size:0.87rem; color:#CBD5E1; line-height:1.6;
}
.conf-badge { display:inline-flex; align-items:center; gap:5px;
  padding:3px 10px; border-radius:14px; font-size:0.72rem; font-weight:700; }
.conf-high   { background:rgba(16,185,129,0.12); color:#34D399; border:1px solid rgba(16,185,129,0.25); }
.conf-medium { background:rgba(245,158,11,0.12);  color:#FBBF24; border:1px solid rgba(245,158,11,0.25); }
.conf-low    { background:rgba(239,68,68,0.12);   color:#F87171; border:1px solid rgba(239,68,68,0.25); }
.chart-section-label {
  font-size:0.72rem; font-weight:700; color:#6366F1;
  text-transform:uppercase; letter-spacing:1px;
  margin:14px 0 8px 0; padding-bottom:5px;
  border-bottom:1px solid rgba(99,102,241,0.15);
}
@media (max-width: 480px) {
  .ic { padding: 8px 10px !important; }
  .ic-label { font-size: 0.6rem !important; }
  .ic-title { font-size: 0.78rem !important; }
  .ic-body { font-size: 0.72rem !important; }
  .narrative-box { padding: 8px 10px !important; font-size: 0.78rem !important; }
  .chart-section-label { font-size: 0.68rem !important; margin: 8px 0 4px 0 !important; }
}
</style>
"""

_MULTI_CHART_CSS = """
<style>
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 4px; background: rgba(15,23,42,0.6);
    border-radius: 10px; padding: 4px;
    border: 1px solid #1E293B; flex-wrap: wrap;
}
div[data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 7px; padding: 5px 14px;
    font-weight: 600; font-size: 0.82rem; color: #64748B; background: transparent;
}
div[data-testid="stTabs"] [aria-selected="true"] {
    background: linear-gradient(135deg, #6366F1, #8B5CF6) !important;
    color: white !important; box-shadow: 0 3px 10px rgba(99,102,241,0.35);
}

/* ── Responsive Charts ── */
@media (max-width: 768px) {
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        padding: 2px !important;
        border-radius: 8px !important;
        gap: 2px !important;
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        justify-content: space-between !important;
        overflow: hidden !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-list"]::-webkit-scrollbar {
        display: none !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"] {
        padding: 5px 2px !important;
        font-size: 0.68rem !important;
        white-space: nowrap !important;
        flex: 1 1 0% !important;
        min-width: 0 !important;
        max-width: none !important;
        text-align: center !important;
        justify-content: center !important;
        margin: 0 !important;
    }
    .chart-section-label { font-size: 0.68rem !important; margin: 10px 0 6px 0 !important; }
    .narrative-box { padding: 10px 12px !important; font-size: 0.82rem !important; }
    .ic { min-width: 100% !important; padding: 10px 12px !important; }
    .ic-title { font-size: 0.78rem !important; }
    .ic-body { font-size: 0.72rem !important; }
    div[data-testid="stPlotlyChart"] .modebar-container {
        display: none !important;
    }
    div[data-testid="stPlotlyChart"] .modebar {
        display: none !important;
    }
}
@media (max-width: 480px) {
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        padding: 2px !important;
        gap: 1px !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab"] {
        padding: 4px 1px !important;
        font-size: 0.60rem !important;
    }
}
</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Insight / narrative / confidence sub-renderers
# ─────────────────────────────────────────────────────────────────────────────
def _render_insight_cards(insight_cards: List[Dict[str, str]]) -> None:
    if not insight_cards:
        return
    st.markdown("<div class='chart-section-label'>AI Insights</div>", unsafe_allow_html=True)
    cols = st.columns(min(len(insight_cards), 3))
    label_map = {"trend": "Trend", "top_performer": "Top Performer", "anomaly": "Anomaly"}
    for i, card in enumerate(insight_cards[:6]):
        sev  = card.get("severity", "neutral")
        ctype = card.get("type", "insight")
        lbl  = label_map.get(ctype, "Insight")
        html = (
            f"<div class='ic ic-{sev}'>"
            f"<div class='ic-label'>{lbl}</div>"
            f"<div class='ic-title'>{card.get('title', '')}</div>"
            f"<div class='ic-body'>{card.get('body', '')}</div>"
            f"</div>"
        )
        with cols[i % min(len(insight_cards), 3)]:
            st.markdown(html, unsafe_allow_html=True)


def _render_narrative(narrative: str) -> None:
    if not narrative or narrative.strip() in ("Execute the query to generate data-driven insights.", ""):
        return
    st.markdown(
        f"<div class='narrative-box'><strong>Executive Summary</strong><br>{narrative}</div>",
        unsafe_allow_html=True,
    )


def _render_confidence(score: Optional[float], label: Optional[str]) -> None:
    pass



# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────
def render_chart(
    data: List[Dict[str, Any]],
    recommended_chart: Optional[str] = None,
    chart_justification: Optional[str] = None,
    insight_cards: Optional[List[Dict]] = None,
    narrative: Optional[str] = None,
    confidence_score: Optional[float] = None,
    confidence_label: Optional[str] = None,
    user_query: str = "",
) -> None:
    """Render the premium multi-chart panel + AI insights.

    The AI-recommended chart is the first tab (marked ★) and auto-selected.
    All other compatible chart types are available as switchable tabs.
    """
    st.markdown(_INSIGHT_CSS, unsafe_allow_html=True)
    st.markdown(_MULTI_CHART_CSS, unsafe_allow_html=True)

    if isinstance(data, pd.DataFrame):
        if data.empty:
            st.info("No data returned — try a different query.")
            return
        df = data
    else:
        if not data:
            st.info("No data returned — try a different query.")
            return
        df = pd.DataFrame(data)

    if df.empty:
        st.info("Empty result set.")
        return

    # ── 1. Confidence badge ───────────────────────────────────────────────────
    _render_confidence(confidence_score, confidence_label)

    # ── 2. Determine best chart & full eligible list ──────────────────────────
    # _eligible_charts now returns charts sorted by score (best first).
    # We only need to move the AI-recommended chart to front if provided.
    eligible = _eligible_charts(df, user_query)

    # Resolve the best chart via priority chain (AI rec → heuristic → first eligible)
    best_key = _resolve_best_chart(df, recommended_chart, user_query, eligible)

    # Ensure best_key is at position 0 (scoring usually handles this;
    # this step only matters when the AI overrides the local scorer)
    eligible_keys = [k for k, _ in eligible]
    if best_key in eligible_keys and eligible_keys[0] != best_key:
        eligible = [(k, l) for k, l in eligible if k == best_key] + \
                   [(k, l) for k, l in eligible if k != best_key]
    elif best_key not in eligible_keys:
        # AI recommended a type not naturally eligible — prepend it
        for key, label in _ALL_CHART_TYPES:
            if key == best_key:
                eligible = [(key, label)] + eligible
                break

    # ── 3. Visualization header ───────────────────────────────────────────────
    st.markdown("<div class='chart-section-label'>Visualization</div>", unsafe_allow_html=True)

    # ── 4. Build tab labels — mark the first (best) tab with ★ ──────────────
    tab_labels = [
        f"★ {label}" if i == 0 else label
        for i, (key, label) in enumerate(eligible)
    ]

    # ── 5. Render tabs ────────────────────────────────────────────────────────
    if len(eligible) <= 1:
        key, label = eligible[0]
        fn = _BUILDER_MAP.get(key)
        if fn:
            try:
                st.plotly_chart(fn(df, user_query), use_container_width=True)
            except Exception as exc:
                st.warning(f"Chart could not be rendered: {exc}")
        else:
            st.info("No compatible chart for this result. View data in the Result Table above.")
    else:
        chart_tabs = st.tabs(tab_labels)
        for tab, (key, label) in zip(chart_tabs, eligible):
            fn = _BUILDER_MAP.get(key)
            with tab:
                if fn is None:
                    st.info("View data in the Result Table section above.")
                else:
                    try:
                        st.plotly_chart(fn(df, user_query), use_container_width=True)
                    except Exception as exc:
                        st.info(f"Cannot render {label}: {exc}")

    # ── 6. AI Narrative ───────────────────────────────────────────────────────
    if narrative:
        _render_narrative(narrative)

    # ── 7. Insight cards ──────────────────────────────────────────────────────
    if insight_cards:
        _render_insight_cards(insight_cards)
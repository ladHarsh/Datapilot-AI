"""
Result Table — DataPilot AI
Premium styled query results panel with row count badge.
"""
import streamlit as st
import pandas as pd


_CSS = """
<style>
.result-section-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: #6366F1;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 4px 0 8px 0;
    padding-bottom: 5px;
    border-bottom: 1px solid rgba(99,102,241,0.15);
    display: flex;
    align-items: center;
    gap: 8px;
}
.result-row-badge {
    background: rgba(99,102,241,0.15);
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 10px;
    padding: 1px 8px;
    font-size: 0.68rem;
    color: #A78BFA;
    font-weight: 600;
}

/* ── Responsive Result Table ── */
@media (max-width: 768px) {
    .result-section-label {
        font-size: 0.68rem !important;
        margin: 2px 0 6px 0 !important;
        gap: 6px !important;
    }
    .result-row-badge {
        font-size: 0.62rem !important;
        padding: 1px 6px !important;
    }
}
@media (max-width: 480px) {
    .result-section-label {
        font-size: 0.65rem !important;
        margin: 2px 0 4px 0 !important;
        gap: 4px !important;
    }
    .result-row-badge {
        font-size: 0.58rem !important;
        padding: 1px 4px !important;
    }
}
</style>
"""


def render_result_table(data) -> None:
    """Render a premium query result table with row count."""
    st.markdown(_CSS, unsafe_allow_html=True)

    if not data:
        st.markdown("""
        <div style='background:rgba(245,158,11,0.07); border:1px solid rgba(245,158,11,0.2);
            border-radius:10px; padding:14px 18px; font-size:0.84rem; color:#FBBF24;'>
            <b>⚠ Query executed successfully — 0 rows matched.</b><br>
            <span style='font-size:0.78rem; color:#94A3B8; margin-top:4px; display:block;'>
            The SQL was valid and ran without errors, but no records in your database
            satisfy all of the specified conditions simultaneously.<br>
            <b>Tip:</b> Try relaxing one or more filters (e.g. lower the minimum order count,
            reduce category threshold, or broaden the product criteria).
            </span>
        </div>""", unsafe_allow_html=True)
        return

    df = pd.DataFrame(data)
    row_count = len(df)

    st.markdown(
        f"<div class='result-section-label'>Query Results "
        f"<span class='result-row-badge'>{row_count:,} rows</span></div>",
        unsafe_allow_html=True,
    )

    # Convert to string to force left-alignment in Streamlit's data grid
    display_df = df.fillna("").astype(str)
    st.dataframe(display_df, use_container_width=True, hide_index=True)
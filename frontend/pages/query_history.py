import streamlit as st
from components.sidebar import render_sidebar
from components.history_card import render_history_card


def show_query_history():
    render_sidebar()

    st.title(" Query History")

    if not st.session_state.get("connected"):
        st.info("Please connect a database first to view query history.")
        return

    db_info = st.session_state.get("db_info", {})
    current_db = db_info.get("database", "")
    history = [
        item for item in st.session_state.get("query_history", [])
        if item.get("database_name") == current_db
    ]

    if not history:
        st.info(f"No query history available for database '{current_db}'.")
        return

    for item in reversed(history):
        render_history_card(
            item["query"],
            item["sql"],
            item["timestamp"]
        )
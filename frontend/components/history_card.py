import streamlit as st


def render_history_card(query, sql, timestamp):

    with st.container():

        st.markdown("---")

        st.markdown("###  User Query")
        st.write(query)

        st.markdown("###  Generated SQL")
        st.code(sql, language="sql")

        st.caption(f"Executed at: {timestamp}")
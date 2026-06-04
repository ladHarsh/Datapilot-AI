import streamlit as st


def initialize_session():

    default_states = {
        "connected":            False,
        "db_info":              {},
        "schema_data":          None,
        "schema_raw":           {},
        "schema_loaded":        False,
        "schema_load_error":    None,
        "db_stats":             {},
        "query_suggestions":    [],
        "query_result":         None,
        "generated_sql":        "",
        "query_history":        [],
        "chart_type":           None,
        "authenticated":        False,
        "remember_me":          False,
        "theme":                "Light",
        "menu":                 "Dashboard",
        "show_edit_profile":    False,
        "show_change_password": False,
        # Query workspace
        "current_query":        "",
        "last_result":          None,
        "voice_state":          "idle",
        "voice_corrections":    [],
        "_focus_after_suggestion": False,
        # Persistence load flags (reset each new browser session)
        "_settings_loaded":     False,
        "_history_loaded":      False,
        "_connection_restored":  False,
        "_token_refreshed":      False,
        "_fresh_login":          False,



    }

    for key, value in default_states.items():

        if key not in st.session_state:

            st.session_state[key] = value
            
import json
import os
import streamlit as st

DEFAULT_SETTINGS = {
    "theme": "Dark (Default)",
    "sidebar_mode": "Expanded",
    "ai_model": "Gemini",
    "explanation_mode": "Detailed",
    "chart_preference": "Auto (AI Recommended)",
    "auto_insights": True,
    "safe_mode": False,
    "row_limit_mode": "Auto",
    "row_limit": 100,
    "auto_visualization": True,
    "activity_timeline": [],
}

# Path to the persistent settings JSON file (relative to this file → frontend/)
_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "user_settings.json")


def _read_settings_file() -> dict:
    """Read the full settings JSON file (returns {} on any error)."""
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _write_settings_file(data: dict) -> None:
    """Atomically write the full settings JSON file."""
    try:
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def load_settings_from_file(username: str) -> None:
    """Load persisted settings for *username* into session_state.
    Called once after authentication to restore settings across page refreshes.
    """
    all_settings = _read_settings_file()
    user_settings = all_settings.get(username, {})
    if "settings" not in st.session_state:
        st.session_state["settings"] = DEFAULT_SETTINGS.copy()
    # Merge saved values on top of defaults (so new keys always have a default)
    for k, v in user_settings.items():
        if k in DEFAULT_SETTINGS:
            st.session_state["settings"][k] = v


def save_settings_to_file(username: str) -> None:
    """Persist the current settings for *username* to disk."""
    if not username:
        return
    all_settings = _read_settings_file()
    all_settings[username] = st.session_state.get("settings", DEFAULT_SETTINGS.copy())
    _write_settings_file(all_settings)


def initialize_settings():
    """Injects default settings into session_state if they don't exist."""
    if "settings" not in st.session_state:
        st.session_state["settings"] = DEFAULT_SETTINGS.copy()
    else:
        # Ensure any missing keys from updates are added
        for k, v in DEFAULT_SETTINGS.items():
            if k not in st.session_state["settings"]:
                st.session_state["settings"][k] = v


def get_setting(key: str):
    """Retrieve a setting safely."""
    if "settings" not in st.session_state:
        initialize_settings()
    return st.session_state["settings"].get(key, DEFAULT_SETTINGS.get(key))


def save_setting(key: str, value):
    """Update a setting and persist it to disk."""
    if "settings" not in st.session_state:
        initialize_settings()
    st.session_state["settings"][key] = value
    username = st.session_state.get("user_profile", {}).get("username", "")
    save_settings_to_file(username)


def reset_settings():
    """Reset all settings to default."""
    st.session_state["settings"] = DEFAULT_SETTINGS.copy()
    username = st.session_state.get("user_profile", {}).get("username", "")
    save_settings_to_file(username)


def sync_widget(setting_key: str, widget_key: str):
    """Callback to sync a widget's session_state back to the global settings dict."""
    if widget_key in st.session_state:
        save_setting(setting_key, st.session_state[widget_key])


def log_activity(event_text: str):
    """Log an activity event chronologically with timestamp."""
    import datetime
    
    # Get current list of activities
    timeline = get_setting("activity_timeline")
    if not isinstance(timeline, list):
        timeline = []
        
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Append the new event
    timeline.append({
        "text": event_text,
        "time": now_str
    })
    
    # Keep only the last 15 events to avoid bloating the settings file
    timeline = timeline[-15:]
    
    # Save the updated list
    save_setting("activity_timeline", timeline)

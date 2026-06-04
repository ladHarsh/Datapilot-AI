import requests
import streamlit as st
from services.api_client import BASE_URL, get_headers

def get_query_history(page=1, page_size=20):
    try:
        response = requests.get(
            f"{BASE_URL}/history",
            params={"page": page, "page_size": page_size},
            headers=get_headers(),
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("items", [])
        return []
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []

def replay_query(history_id, db_info):
    try:
        response = requests.post(
            f"{BASE_URL}/history/replay",
            json={"history_id": history_id, **db_info},
            headers=get_headers(),
            timeout=30
        )
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

def delete_history_item(history_id):
    try:
        response = requests.delete(
            f"{BASE_URL}/history/{history_id}",
            headers=get_headers(),
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        return False

def clear_query_history():
    try:
        response = requests.delete(
            f"{BASE_URL}/history",
            headers=get_headers(),
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Error clearing history: {e}")
        return False
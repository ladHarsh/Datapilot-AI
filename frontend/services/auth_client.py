import os
import requests
import streamlit as st

backend_url = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").strip()
if not backend_url.startswith(("http://", "https://")):
    backend_url = f"http://{backend_url}"
backend_url = backend_url.rstrip("/")
if backend_url.endswith("/api/v1"):
    backend_url = backend_url[:-7]
BASE_URL = backend_url + "/api/v1/auth"

def signup_user(username, email, password):
    try:
        response = requests.post(
            f"{BASE_URL}/signup",
            json={
                "username": username,
                "email": email,
                "password": password
            },
            timeout=12
        )
        if response.status_code == 201:
            return True, "Success"
        elif response.status_code in (502, 503, 504):
            return False, "⏳ The backend database engine is waking up from sleep (Render free tier cold-start takes ~50 seconds). Please try again in a moment."
        elif response.status_code == 400:
            return False, response.json().get("detail", "Signup failed")
        else:
            return False, f"Server error: {response.status_code}"
    except Exception:
        return False, "⏳ The backend database engine is waking up from sleep or connection failed. Please wait a moment and try again."

def login_user(username, password):
    try:
        # FastAPI OAuth2PasswordRequestForm expects form data
        response = requests.post(
            f"{BASE_URL}/login",
            data={
                "username": username,
                "password": password
            },
            timeout=12
        )
        if response.status_code == 200:
            data = response.json()
            # Store the token in session state
            st.session_state["access_token"] = data.get("access_token")
            
            # Fetch user info using the token
            me_response = requests.get(
                f"{BASE_URL}/me",
                headers={"Authorization": f"Bearer {data.get('access_token')}"},
                timeout=5
            )
            
            if me_response.status_code == 200:
                user_data = me_response.json().get("data", {})
                return {"success": True, "user": user_data}
 
            detail = "Session validation failed"
            try:
                detail = me_response.json().get("detail", detail)
            except Exception:
                pass
            return {"success": False, "error": detail}
                
        elif response.status_code in (502, 503, 504):
            return {"success": False, "error": "⏳ The backend database engine is waking up from sleep (Render free tier cold-start takes ~50 seconds). Please try again in a moment."}
        elif response.status_code == 401:
            return {"success": False, "error": "Invalid credentials."}
        else:
            return {"success": False, "error": f"Server error: {response.status_code}"}
    except Exception:
        return {"success": False, "error": "⏳ The backend database engine is waking up from sleep or connection failed. Please wait a moment and try again."}

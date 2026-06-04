import requests

from services.api_client import BASE_URL, get_headers, _parse_response


def fetch_user_profile() -> dict:
    """Load the logged-in user's profile from the API."""
    try:
        response = requests.get(
            f"{BASE_URL}/profile",
            headers=get_headers(),
            timeout=10,
        )
        parsed = _parse_response(response)
        if parsed.get("success"):
            return {"success": True, "data": parsed.get("data", {})}
        return {"success": False, "error": parsed.get("message", "Failed to load profile.")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_user_profile(full_name: str | None = None, email: str | None = None) -> dict:
    """PATCH profile fields."""
    payload = {}
    if full_name is not None:
        payload["full_name"] = full_name.strip() or None
    if email is not None:
        payload["email"] = email.strip()

    try:
        response = requests.patch(
            f"{BASE_URL}/profile",
            json=payload,
            headers=get_headers(),
            timeout=10,
        )
        parsed = _parse_response(response)
        if parsed.get("success"):
            return {"success": True, "data": parsed.get("data", {})}
        return {"success": False, "error": parsed.get("message", "Update failed.")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def change_password(current_password: str, new_password: str) -> dict:
    """Change the user's password."""
    try:
        response = requests.post(
            f"{BASE_URL}/profile/change-password",
            json={
                "current_password": current_password,
                "new_password": new_password,
            },
            headers=get_headers(),
            timeout=10,
        )
        parsed = _parse_response(response)
        if parsed.get("success"):
            return {"success": True, "message": parsed.get("message", "Password changed.")}
        return {"success": False, "error": parsed.get("message", "Password change failed.")}
    except Exception as e:
        return {"success": False, "error": str(e)}

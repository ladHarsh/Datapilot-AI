import requests
from services.api_client import BASE_URL, get_headers

def export_to_csv(data, columns, filename="export"):
    try:
        response = requests.post(
            f"{BASE_URL}/export/csv",
            json={"columns": columns, "rows": data, "filename": filename},
            headers=get_headers(),
            timeout=15
        )
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        print(f"Export CSV error: {e}")
        return None

def export_to_excel(data, columns, filename="export"):
    try:
        response = requests.post(
            f"{BASE_URL}/export/excel",
            json={"columns": columns, "rows": data, "filename": filename},
            headers=get_headers(),
            timeout=15
        )
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        print(f"Export Excel error: {e}")
        return None
import requests
import sqlite3

# Aapki API ka URL aur Key yahan aayegi
API_URL = "https://your-api-endpoint.com/v1/sync"
API_KEY = "YOUR_PRIVATE_ACCESS_KEY"

def start_cloud_sync(local_id, data_payload):
    """
    Yeh function check karega ki internet hai ya nahi, 
    agar hai toh aapke private API par data bhej dega.
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "device_id": local_id,
        "data": data_payload
    }

    try:
        # 3 second ka timeout taaki agar net slow ho toh app hang na ho
        response = requests.post(API_URL, json=payload, headers=headers, timeout=3)
        
        if response.status_code == 200:
            return True # Sync Successful
        return False
    except requests.exceptions.RequestException:
        return False # Offline mode
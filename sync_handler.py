import requests
import json
import os
import time

# Configurations
API_URL = "https://jarvis-advanced-api.onrender.com"
API_KEY =  "4155f1d03eee301be4b4ea7ea7926b37"  # Jo key generate ki thi wo dalo
LOCAL_CACHE_FILE = "offline_sync_cache.json"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def save_offline_data(data_payload):
    """Agar internet nahi hai toh data ko local file mein save karo"""
    existing_data = []
    if os.path.exists(LOCAL_CACHE_FILE):
        try:
            with open(LOCAL_CACHE_FILE, "r") as f:
                existing_data = json.load(f)
        except:
            existing_data = []
            
    existing_data.append({
        "timestamp": time.time(),
        "payload": data_payload
    })
    
    with open(LOCAL_CACHE_FILE, "w") as f:
        json.dump(existing_data, f, indent=4)
    print("💾 Data offline save kar diya gaya hai (Cache).")

def sync_data_online(device_id, payload_data):
    """Local device se data online Render server par bhejna"""
    url = f"{API_URL}/sync"
    
    # Swagger UI ke mutabik payload structure
    data = {
        "user_id": "sudipta_User",
        "device_id": device_id,
        "data_payload": json.dumps(payload_data),
        "location": "Kolkata"
    }
    
    try:
        print("⏳ Server par data sync ho raha hai...")
        response = requests.post(url, json=data, headers=HEADERS)
        
        if response.status_code == 200:
            print("🟢 Sync Successful! Data online server par save ho gaya.")
            return True
        else:
            print(f"⚠️ Server Response Code: {response.status_code}")
            save_offline_data(payload_data)
            return False
    except Exception as e:
        print("❌ Internet issue! Data online nahi jaa paya.")
        save_offline_data(payload_data)
        return False

if __name__ == "__main__":
    # Test karne ke liye ek dummy command sync karke dekhte hain
    print("⚡ Jarvis Sync Handler Initializing...")
    test_command = {"command": "open youtube", "status": "executed_successfully"}
    
    # Apne PC ka ek naam de do (jaise 'My_Dell_Laptop')
    sync_data_online(device_id="My_Dell_Laptop", payload_data=test_command)
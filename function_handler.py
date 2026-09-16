import sqlite3
import json
import requests
from datetime import datetime

class JarvisOrchestrator:
    def __init__(self, db_name="jarvis_memory.db"):
        self.db_name = db_name
        self.registry = {}

    def register(self, name=None):
        def decorator(func):
            func_id = name if name else func.__name__
            self.registry[func_id] = func
            return func
        return decorator

    def call(self, func_name, **kwargs):
        status = "SUCCESS"
        if func_name not in self.registry:
            return f"Error: Command '{func_name}' not found."
        
        try:
            # Function ko execute karna
            result = self.registry[func_name](**kwargs)
        except Exception as e:
            # Agar koi error aaye toh system crash nahi hoga
            result = f"Failed Execution: {str(e)}"
            status = "FAILED"
        
        # Database mein entry (Log)
        self.log_to_db(func_name, result, status)
        return result

    def log_to_db(self, func_name, result, status):
        """Premium Logging: Har action ka status save hota hai."""
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("""
                INSERT INTO call_logs (func_name, result, time) 
                VALUES (?, ?, ?)
            """, (func_name, f"[{status}] {str(result)}", datetime.now()))

# Initialize Engine
jarvis_engine = JarvisOrchestrator()

# --- AB YAHAN APNI CUSTOM API ADD KAREIN ---

@jarvis_engine.register(name="fetch_online_data")
def fetch_online_data(api_key, endpoint):
    """
    Yeh function Online aur Offline dono kaam karega.
    Agar internet nahi hai, toh error log karega.
    """
    url = f"https://api.example.com/{endpoint}" # Apna URL yahan dalein
    headers = {"Authorization": f"Bearer {api_key}"}
    
    response = requests.get(url, headers=headers, timeout=5)
    return response.json()
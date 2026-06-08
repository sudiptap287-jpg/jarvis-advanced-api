import asyncio
import time
import hashlib
import os
import secrets
import sys
import io
import geoip2.database
import httpx
import datetime
import re
from sqlalchemy import text 
from typing import List
from fastapi import FastAPI, Depends, WebSocket, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, String, Integer, Boolean, Float, Text, LargeBinary, DateTime
from contextlib import asynccontextmanager
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from security_logic import encrypt_now, check_online
from security_utils import PremiumEngine
from datetime import datetime
from fastapi import BackgroundTasks
from map_logic import PremiumMapEngine
from fastapi.responses import HTMLResponse
from sync_handler import sync_data_online

# --- GLOBAL HEARTBEAT VARIABLES ---
LAST_SEEN_LAPTOP = time.time()  # Shuru mein current time set rahega
MY_PERMANENT_KEY = "jarvis_super_secret_2026_key"  # Tumhari permanent owner key

# --- 3. FASTAPI APP INITIALIZATION ---
app = FastAPI(title="Jarvis Advanced API 2.0", version="2.0.0")

@app.get("/") 
async def home():
    return {"status": "Jarvis API 2.0 Running", "documentation": "/docs"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Logic ---
    db = SessionLocal()
    
    # 1. Master key check/create
    if not os.path.exists("master_access.key"):
        with open("master_access.key", "w") as f:
            f.write("jarvis_default_master_secure_lock_2026")
    
    # 2. Database mein Default API Key check/create
    # Yahan 'f2b337...' ki jagah apni wahi key likho jo jarvis_core.py mein hai
    existing_key = db.query(APIKey).filter(APIKey.key_value == "f2b337...").first()
    if not existing_key:
        new_key = APIKey(key_value="f2b337...", owner="sudipto", is_active=True)
        db.add(new_key)
        db.commit()
        print("🔑 Database reset hua tha, isliye default API Key re-created!")
    
    db.close()
    asyncio.create_task(auto_sync_worker())
    
    yield # App chal rahi hai
    
    # --- Shutdown Logic ---
    pass

# --- 1. DATABASE SETUP (DYNAMIC SWITCH TO POSTGRESQL) ---
# Online server (Render) par 'DATABASE_URL' environment variable milega, local par ye SQLite chalayega
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./jarvis_ai.db")

# Render ka PostgreSQL URL 'postgres://' se shuru hota hai, par SQLAlchemy ko 'postgresql://' chahiye hota hai
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Connect arguments sirf SQLite ke liye chahiye hote hain
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- DEPENDENCY ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 2. DATABASE MODELS ---
class AudioRecord(Base):
    __tablename__ = "audio_records"
    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, unique=True, index=True)
    status = Column(String, default="recording")
    timestamp = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    credits = Column(Float, default=100.0)

class OfflineMapCache(Base):
    __tablename__ = "map_cache"
    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, unique=True, index=True)
    data = Column(Text)  

class DeviceSyncLog(Base):
    __tablename__ = "device_sync_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    device_id = Column(String)
    sync_data_id = Column(String, nullable=True)
    status = Column(String, default="offline_ready")
    last_sync_time = Column(Float)
    Local_changes = Column(Integer, default=0)
    data_payload = Column(LargeBinary)

class CodeExecutionTask(Base):
    __tablename__ = "code_executions"
    id = Column(Integer, primary_key=True, index=True)
    code_input = Column(Text)
    result_output = Column(Text)
    execution_time = Column(DateTime, default=datetime.utcnow)

class BillingTransaction(Base):
    __tablename__ = "billing_transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    amount_deducted = Column(Float)
    feature_used = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class RestrictedZone(Base):
    __tablename__ = "restricted_zones"
    country_code = Column(String, primary_key=True, index=True)
    zone_name = Column(String)
    reason = Column(String, default="Region Blocked")

class GeoAccessLog(Base):
    __tablename__ = "geo_access_logs"
    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, index=True)
    country = Column(String)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class AccessLog(Base):
    __tablename__ = "access_logs"
    id = Column(Integer, primary_key=True)
    api_key = Column(String)
    timestamp = Column(Float)

class PromptCache(Base):
    __tablename__ = "prompt_cache"
    hash = Column(String, primary_key=True, index=True)
    prompt = Column(String)
    response = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class APIKey(Base):
    __tablename__ = "api_key"
    id = Column(Integer, primary_key=True, index=True)
    key_value = Column(String, unique=True, index=True)
    owner = Column(String)
    usage_limit = Column(Integer, default=1000)
    current_usage = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

Base.metadata.create_all(bind=engine)

# --- SECURITY UTILS ---
premium_engine = PremiumEngine(master_key="your_own_master_key")

def rate_limit_gate(api_key: str, db: Session):
    window = 60  
    limit = 10   
    now = time.time()
    
    db.execute(text("DELETE FROM access_logs WHERE timestamp < :cutoff"), {"cutoff": now - window})
    db.commit()
    
    usage_count = db.query(AccessLog).filter(AccessLog.api_key == api_key).count() 
    
    if usage_count >= limit:
        raise HTTPException(status_code=429, detail="Premium Rate Limit Exceeded. Please wait.")
    
    return True

# --- 4. PYDANTIC SCHEMAS ---
class UserAuth(BaseModel):
    email: EmailStr
    password: str

class SyncRequest(BaseModel):
    user_id: str
    device_id: str
    data_payload: str
    sync_data_payload: str = None

# --- ROUTES ---
@app.post("/sync")
async def sync_data(sync_data: SyncRequest, db: Session = Depends(get_db)): 
    secure_blob = premium_engine.pack_data(sync_data.data_payload)
    
    new_log = DeviceSyncLog(
        user_id=sync_data.user_id,
        device_id=sync_data.device_id,
        data_payload=secure_blob, 
        last_sync_time=time.time()
    )
    
    db.add(new_log)
    db.commit()
    return {"status": "success", "info": "Data Secured & Cached"}


class NativePremiumEngine:
    def execute_logic(self, command):
        cmd = command.lower()
        if "status" in cmd:
            return "System: 100% Operational | Mode: Native Premium"
        elif "sync" in cmd:
            return "Database Sync: Local Vault Secured"
        else:
            return f"Native Execution: Task '{command}' logged."

native_engine = NativePremiumEngine()

@app.websocket("/ws/live")
async def live_chat(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        response = native_engine.execute_logic(data)
        await websocket.send_text(response)
    
@app.websocket("/ws/audio")
async def real_time_audio_api(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    save_directory = "audio_storage"
    os.makedirs(save_directory, exist_ok=True)
    
    file_name = f"stream_{int(time.time())}.raw"
    file_path = os.path.join(save_directory, file_name)
    
    new_audio_log = AudioRecord(file_path=file_path, status="recording_started")
    db.add(new_audio_log)
    db.commit()
    
    try:
        with open(file_path, "wb") as audio_file:
            while True:
                audio_chunk = await websocket.receive_bytes()
                audio_file.write(audio_chunk)
                await websocket.send_text("Audio chunk securely received and saved locally.")
    except Exception as e:
        print(f"Audio stream ended or interrupted: {e}")
        new_audio_log.status = "saved_offline_locally"
        db.commit()

async def process_my_own_api_batch(data_items: list, db: Session):
    for entry in data_items:
        new_entry = DeviceSyncLog(
            user_id=entry.get('user_id'),
            sync_data_id=f"LOCAL_{int(time.time())}_{entry.get('user_id')}", 
            data_payload=entry.get('payload'), 
            status="offline_ready", 
            last_sync_time=time.time()
        )
        db.add(new_entry)
    db.commit()

@app.post("/api/v1/internal-batch")
async def internal_batch_handler(
    payload: List[dict], 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    background_tasks.add_task(process_my_own_api_batch, payload, db)
    return {
        "api_status": "active",
        "mode": "local_offline_storage",
        "count": len(payload)
    }

# --- 🛰️ LAPTOP PING ENDPOINT ---
@app.post("/api/ping")
async def receive_ping(provided_key: str):
    global LAST_SEEN_LAPTOP
    if provided_key == MY_PERMANENT_KEY: 
        LAST_SEEN_LAPTOP = time.time()
        return {"status": "Laptop is Online"}
    raise HTTPException(status_code=401, detail="Unauthorized Ping Key")


def my_own_api_logic(prompt):
    command = prompt.lower().strip()

    # --- Identity & Memory ---
    if "who are you" in command or "tum kaun ho" in command:
        return "Main Jarvis hoon, ek advanced private AI assistant. Mera nirmaan Sudipto ne kiya hai."
    
    elif "who is your boss" in command or "creator" in command or "boss" in command:
        return "Mere creator aur Supreme Commander Sudipto hain. Main sirf unhi ke commands follow karta hoon."

    # --- Time & Space Engine ---
    elif "time" in command or "samay" in command:
        now = datetime.datetime.now()
        return f"System clock ke hisaab se abhi {now.strftime('%I:%M %p')} ho raha hai."
        
    elif "date" in command or "aaj kya hai" in command:
        now = datetime.datetime.now()
        return f"Aaj ki tareekh {now.strftime('%d %B %Y')} hai, aur aaj {now.strftime('%A')} hai."

    # --- Smart Math Solver ---
    elif "calculate" in command or "+" in command or "-" in command or "*" in command or "/" in command:
        try:
            math_expr = re.sub('[^0-9\+\-\*\/\(\)\.]', '', command)
            if math_expr:
                result = eval(math_expr)
                return f"Is calculation ka result hai: {result}"
            else:
                return "Aapne koi valid number nahi diya calculation ke liye."
        except Exception:
            return "Sorry, ye calculation samajh nahi aayi. Kripya clear numbers batayein."

    # --- Fallback ---
    else:
        return f"Command received: '{prompt}'. (Yeh request server par log ho gayi hai, iska logic jald hi update hoga.)"
    
def get_or_set_cache(db, user_prompt, api_call_func):
    p_hash = hashlib.sha256(user_prompt.strip().encode('utf-8')).hexdigest()
    cached_item = db.query(PromptCache).filter(PromptCache.hash == p_hash).first()
    
    if cached_item:
        return f"[CACHED] {cached_item.response}"
    
    new_response = api_call_func(user_prompt)
    new_cache = PromptCache(hash=p_hash, prompt=user_prompt, response=new_response)
    db.add(new_cache)
    db.commit()
    return new_response

@app.post("/get_answer")
async def get_answer(prompt: str, db: Session = Depends(get_db)):
    result = get_or_set_cache(db, prompt, my_own_api_logic) 
    return {"status": "success", "data": result}

@app.get("/get_premium_map", response_class=HTMLResponse)
async def get_map(lat: float, lon: float):
    engine_map = PremiumMapEngine(api_key="your_own_api_key")
    map_html = engine_map.generate_map_html(lat, lon)
    return map_html

def verify_api_key(api_key: str, db: Session):
    key = db.query(APIKey).filter(APIKey.key_value == api_key, APIKey.is_active == True).first()
    if not key:
        return False
    return True

def generate_new_key():
    return secrets.token_hex(16)

@app.post("/admin/generate-key")
async def create_api_key(owner_name: str, limit: int = 1000, db: Session = Depends(get_db)):
    new_key_value = generate_new_key()
    new_entry = APIKey(
        key_value=new_key_value,
        owner=owner_name,
        usage_limit=limit,
        current_usage=0,
        is_active=True
    )
    db.add(new_entry)
    db.commit()
    
    return {
        "status": "Key Created",
        "owner": owner_name,
        "api_key": new_key_value,
        "limit": limit
    }
# main.py ke andar
MY_PERMANENT_KEY = "jarvis_super_secret_2026_key" # Ye tumhari permanent key hogi

def validate_api_key(api_key: str, db: Session = Depends(get_db)):
    # 1. Pehle permanent key check karo
    if api_key == MY_PERMANENT_KEY:
        return "Admin_Owner"
    
    # 2. Agar permanent nahi hai, tabhi database mein dhundo
    key = db.query(APIKey).filter(APIKey.key_value == api_key, APIKey.is_active == True).first()
    if not key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    return key.owner

@app.post("/v2/get_answer")
async def get_answer_secure(prompt: str, db: Session = Depends(get_db), owner: str = Depends(validate_api_key)):
    global LAST_SEEN_LAPTOP
    
    # ---- ⏱️ STOPWATCH CHECK YAHAN FUNCTION KE ANDAR paste karo ----
    current_time = time.time()
    if current_time - LAST_SEEN_LAPTOP > 45:
        raise HTTPException(status_code=403, detail="Access Denied: Server is locked because laptop is disconnected.")
    # ---------------------------------------------------------------

    # Iske neeche tumhara baaki ka purana code waisa hi chalne do...
    result = get_or_set_cache(db, prompt, my_own_api_logic) 
    return {
        "status": "success",
        "authorized_user": owner,
        "data": result
    }

class PremiumInterpreterEngine:
    def __init__(self):
        self.state = {}
        self.common_fixes = {
            "math": "import math",
            "json": "import json",
            "os": "import os",
            "datetime": "from datetime import datetime"
        }

    def try_auto_fix(self, error_msg, code_str):
        if "is not defined" in error_msg:
            missing_var = error_msg.split("'")[1]
            if missing_var in self.common_fixes:
                fixed_code = f"{self.common_fixes[missing_var]}\n{code_str}"
                return fixed_code, f"Auto-Fixed: Added missing import for '{missing_var}'"
        
        if "expected an indented block" in error_msg:
            return None, "Indentation Error detected. Please check your code blocks."
        return None, "No local fix found for this error."

    def run_safe_code(self, code_str: str):
        output_capture = io.StringIO()
        sys.stdout = output_capture
        status_note = "Original Execution"
        
        try:
            exec(code_str, self.state)
            result = output_capture.getvalue()
        except Exception as e:
            error_msg = str(e)
            fixed_code, fix_status = self.try_auto_fix(error_msg, code_str)
            if fixed_code:
                try:
                    output_capture = io.StringIO() 
                    sys.stdout = output_capture
                    exec(fixed_code, self.state)
                    result = output_capture.getvalue()
                    status_note = fix_status
                except Exception as e2:
                    result = f"Fix Attempt Failed: {str(e2)}"
                    status_note = "Auto-fix failed"
            else:
                result = f"Error: {error_msg}"
                status_note = "Manual correction needed"
        finally:
            sys.stdout = sys.__stdout__
        
        return result or "Task Completed.", status_note
    
interpreter_engine = PremiumInterpreterEngine()

class PremiumBillingSystem:
    def __init__(self):
        self.rates = {
            "code_execution": 0.50,  
            "map_view": 1.00,        
            "audio_sync": 0.10       
        }

    def process_billing(self, user_id: str, feature: str, db: Session):
        cost = self.rates.get(feature, 0.05)
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.credits -= cost 
            new_tx = BillingTransaction(
                user_id=user_id,
                amount_deducted=cost,
                feature_used=feature
            )
            db.add(new_tx)
            db.commit()
            return True, cost
        return False, 0

billing_engine = PremiumBillingSystem()

@app.post("/execute")
async def premium_control_center(request: Request, command: str, api_key: str, db: Session = Depends(get_db)):
    rate_limit_gate(api_key, db) 
    success, cost = billing_engine.process_billing("ADMIN", "code_execution", db)

    if not os.path.exists("master_access.key"):
        return {"error": "Unauthorized"}

    output, fix_log = interpreter_engine.run_safe_code(command)

    new_task = CodeExecutionTask(
        code_input=command, 
        result_output=f"[{fix_log}] {output}"
    )
    db.add(new_task)
    db.commit()

    return {
        "status": "Premium_Active",
        "fix_status": fix_log,
        "output": output,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

def check_geo_restriction(ip_address: str, db: Session):
    try:
        with geoip2.database.Reader('GeoLite2-Country.mmdb') as reader:
            response = reader.country(ip_address)
            user_country = response.country.iso_code
    except Exception:
        user_country = "UNKNOWN"  
        
    is_blocked = db.query(RestrictedZone).filter(RestrictedZone.country_code == user_country).first()
    if is_blocked:
        return False, user_country
    return True, user_country  

async def auto_sync_worker():
    while True:
        db = SessionLocal() 
        try:
            pending_tasks = db.query(DeviceSyncLog).filter(
                DeviceSyncLog.status == "offline_ready"
            ).all()
            
            if pending_tasks:
                print(f"🔄 Syncing {len(pending_tasks)} offline records...")
                async with httpx.AsyncClient() as client:
                    for task in pending_tasks:
                        try:
                            response = await client.post(
                                "https://your-private-api.com/sync", 
                                json={"data": task.data_payload.decode('utf-8', errors='ignore') if isinstance(task.data_payload, bytes) else task.data_payload},
                                timeout=5.0
                            )
                            if response.status_code == 200:
                                task.status = "synced_online"
                                db.commit()
                        except Exception as mix_e:
                            print(f"🌐 Connection failed, staying offline... {mix_e}")
            
        except Exception as e:
            print(f"❌ Worker Error: {e}")
        finally:
            db.close()
        await asyncio.sleep(30)

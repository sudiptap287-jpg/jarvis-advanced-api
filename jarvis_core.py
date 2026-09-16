import requests
import time
import pyttsx3
import webbrowser
import random
import math
import re
import os
import datetime
import psutil
import speech_recognition as sr
import pyautogui 
import smtplib
import threading
import cv2
import vosk
import sounddevice as sd
import queue
import json
import sys
import screen_brightness_control as sbc
import subprocess
import re
import ollama  
import sys
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt5.QtGui import QMovie, QFont, QColor
# ... baaki ke imports waise hi rahenge ...
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from dotenv import load_dotenv
from email.message import EmailMessage

# NEW: Import the refactored controller classes
from jarvis_modules import (
    HardwareControl, 
    ApplicationControl, 
    SystemInteraction, 
    SystemMaintenance, 
    MemoryManager,
    AdvancedSolver, 
    ScreenVisionControl,
    GUIControl  # <-- Naya GUI Controller import karein
)
# Client script me bhi .env file load karni hogi
load_dotenv()

# Ab hardcoded strings ki jagah in variables ka use karein
API_URL = os.getenv("API_URL")
MY_API_KEY = os.getenv("JARVIS_API_KEY")
MY_EMAIL = os.getenv("SENDER_EMAIL")
MY_EMAIL_PASSWORD = os.getenv("SENDER_PASSWORD")
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

r = sr.Recognizer()
JARVIS_ACTIVE = False 
LAST_PRINTED_MODE = None

# NEW: Instantiate the controller classes
hardware_controller = HardwareControl()
app_controller = ApplicationControl(my_email=MY_EMAIL, my_email_password=MY_EMAIL_PASSWORD)
system_interactor = SystemInteraction()
system_maintainer = SystemMaintenance()
memory_manager = MemoryManager()
solver = AdvancedSolver()
screen_analyzer = ScreenVisionControl() # <-- Naya object initialize karein
gui_controller = GUIControl() # <-- Naya GUI Controller initialize karein

# --- GLOBAL VARIABLES FOR WAKE WORD ENGINE (PERFORMANCE BOOST) ---
VOSK_MODEL = None
WAKE_WORDS = ["jarvis", "wake up"]
# Convert to JSON string for Vosk to create a specific, fast grammar
WAKE_WORD_GRAMMAR = json.dumps(WAKE_WORDS + ["[unk]"])
LLM_CACHE = {} # In-memory cache for LLM responses

def clean_text_for_speech(text):
    text = str(text)
    text = text.replace('*', '').replace('#', '').replace('`', '').replace('_', '')
    text = re.sub(r'[^\x00-\x7F]+', ' ', text) 
    return text

def speak(text):
    print(f"🤖 Jarvis: {text}")
    try:
        engine = pyttsx3.init('sapi5')
        voices = engine.getProperty('voices')
        if len(voices) > 0: engine.setProperty('voice', voices[0].id)
        engine.setProperty('rate', 175)  
        engine.setProperty('volume', 1.0) 
        safe_text = clean_text_for_speech(text)
        if safe_text.strip():  
            engine.say(safe_text)
            engine.runAndWait()
    except Exception as e:
        print(f"⚠️ Voice Error: {e}")

def open_in_chrome(url):
    chrome_paths = [
        "C:/Program Files/Google/Chrome/Application/chrome.exe %s",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe %s"
    ]
    for path in chrome_paths:
        if os.path.exists(path.split(" %s")[0]):
            webbrowser.get(path).open(url)
            return
    webbrowser.open(url)

def play_on_youtube(song_name):
    try:
        search_url = f"https://www.youtube.com/results?search_query={song_name.replace(' ', '+')}"
        response = requests.get(search_url, timeout=5)
        video_ids = re.findall(r"watch\?v=(\S{11})", response.text)
        if video_ids:
            direct_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
            open_in_chrome(direct_url)
            return f"Playing {song_name} on YouTube, Commander."
    except Exception as e:
        print(f"Scraping error: {e}")
    
    open_in_chrome(f"https://www.youtube.com/results?search_query={song_name.replace(' ', '+')}")
    return f"Opening search results for {song_name} in Chrome."

def take_command():
    global LAST_PRINTED_MODE
    with sr.Microphone() as source:
        if not JARVIS_ACTIVE and LAST_PRINTED_MODE != "SLEEP":
            print("\n💤 Sleep Mode... (Bolo 'Hey Jarvis' ya 'Wake Up')")
            LAST_PRINTED_MODE = "SLEEP"
        elif JARVIS_ACTIVE and LAST_PRINTED_MODE != "LISTENING":
            print("\n🎙️ Listening... (Boliye Commander Sudipto)")
            LAST_PRINTED_MODE = "LISTENING"
            
        r.pause_threshold = 0.8
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=7)
            query = r.recognize_google(audio, language='en-in')
            print("⏳ Recognizing...")
            print(f"👉 Detected Input: '{query}'") 
            return query.lower()
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return ""
        except Exception:
            return ""

def system_control(query):
    """
    Delegates the user's command to the appropriate controller module.
    Each controller's handle_query method returns a response if it can handle the command,
    otherwise it returns None, and the next controller is tried.
    """
    query = query.lower()

    response = (
        system_interactor.handle_query(query, take_command, speak) or
        app_controller.handle_query(query, take_command, speak) or
        hardware_controller.handle_query(query, take_command, speak) or
        system_maintainer.handle_query(query, speak) or
        memory_manager.handle_query(query, take_command, speak) or
        screen_analyzer.handle_query(query, speak) or
        gui_controller.handle_query(query) # <-- Naya GUI trigger connect karein
    )
    return response

# === HIGH-PERFORMANCE OFFLINE WAKE WORD ENGINE (VOSK) ===

def initialize_wake_word_engine():
    """Loads the Vosk model into memory ONCE for faster performance."""
    global VOSK_MODEL
    print("🎙️  Initializing Offline Wake Word Engine...")
    try:
        application_path = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        application_path = os.getcwd()
        
    model_path = os.path.join(application_path, "vosk_model")
    
    if not os.path.exists(model_path):
        print(f"\n❌ FATAL ERROR: Vosk model not found at '{model_path}'")
        print("👉 Please download a Vosk model and place it in the 'vosk_model' folder.")
        return False
        
    try:
        vosk.SetLogLevel(-1)
        VOSK_MODEL = vosk.Model(model_path)
        print("✅ Offline Wake Word Engine loaded successfully.")
        return True
    except Exception as e:
        print(f"\n❌ VOSK MODEL LOAD ERROR: {e}")
        VOSK_MODEL = None
        return False

def wait_for_wake_word_offline():
    """
    Listens efficiently for specific wake words using a pre-loaded model.
    This is much faster as it doesn't reload the model every time.
    """
    if not VOSK_MODEL:
        print("❌ Wake word engine is not initialized. Cannot listen.")
        time.sleep(2)
        return False

    print("\n" + "="*50)
    print("💤 SYSTEM IN SLEEP MODE")
    print(f"🎙️  Listening OFFLINE for: {', '.join(WAKE_WORDS)}")
    print("="*50)

    q = queue.Queue()
    def callback(indata, frames, time, status):
        if status:
            print(f"⚠️ Audio Status: {status}", file=sys.stderr)
        q.put(bytes(indata))

    try:
        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16', channels=1, callback=callback):
            # PERFORMANCE BOOST: We provide a specific grammar list.
            # This tells Vosk to ONLY listen for our wake words, making it faster and more accurate.
            rec = vosk.KaldiRecognizer(VOSK_MODEL, 16000, WAKE_WORD_GRAMMAR)
            while True:
                data = q.get()
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "")
                    if any(word in text for word in WAKE_WORDS):
                        print(f"\n✅ WAKE WORD DETECTED: '{text}'! Booting up...")
                        return True
                        
    except Exception as e:
        print(f"\n❌ MICROPHONE ERROR: Is your mic connected? Details: {e}")
        time.sleep(2)
        return False

JARVIS_DICTIONARY = {
    "greetings": {"keywords": ["hello", "hi", "hey", "namaste", "suno"], "responses": ["Hello sir, tell me what I can do for you?"], "action_url": None},
    "youtube": {"keywords": ["open youtube", "youtube kholo"], "responses": ["Opening YouTube."], "action_url": "https://www.youtube.com"},
    "google": {"keywords": ["open google", "google kholo"], "responses": ["Opening Google."], "action_url": "https://www.google.com"}
}

def check_local_dictionary(query):
    for category, data in JARVIS_DICTIONARY.items():
        for keyword in data["keywords"]:
            if keyword in query:
                if data["action_url"]: open_in_chrome(data["action_url"]) 
                return random.choice(data["responses"])
    return None


def get_live_info(query):
    if "time" in query: return f"The time is {datetime.datetime.now().strftime('%I:%M %p')}."
    elif "date" in query: return f"Today is {datetime.datetime.now().strftime('%B %d, %Y')}."
    elif any(word in query for word in ["battery", "power"]):
        try: return f"Battery is at {psutil.sensors_battery().percent} percent."
        except: return "Unable to fetch battery status."
    elif "weather" in query or "temperature" in query:
        # OpenWeatherMap API key (Free tier wali)
        api_key = WEATHER_API_KEY
        # IP-based location nikalne ke liye free API
        try:
            ip_data = requests.get("https://ipinfo.io", timeout=3).json()
            city = ip_data.get("city", "Delhi")
            
            weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
            res = requests.get(weather_url).json()
            
            if res.get("cod") == 200:
                temp = res["main"]["temp"]
                desc = res["weather"][0]["description"]
                return f"Currently in {city}, it is {temp} degrees Celsius with {desc}."
            else:
                return "Weather API configuration error, sir."
        except Exception as e:
            return "Unable to fetch live weather data. Check network connection or API key."
    return None

def get_intelligent_answer(prompt):
    """
    Encapsulates the multi-tiered LLM logic.
    This function is designed to be run in a separate thread to avoid blocking.
    """
    # Priority 1: Check In-Memory Cache
    if prompt in LLM_CACHE:
        print("🧠 Returning answer from local cache...")
        return f"[CACHED] {LLM_CACHE[prompt]}"

    # Priority 2: Ask Local Ollama
    local_answer = ask_ollama_local(prompt)
    if local_answer:
        LLM_CACHE[prompt] = local_answer # Save to cache
        return local_answer
        
    # Priority 3: Fallback to Server's Groq AI
    try:
        print("🌐 Asking Main Server ...")
        response = requests.post(f"{API_URL}/v2/ask_groq", params={"prompt": prompt}, headers={"api_key": MY_API_KEY}, timeout=10)
        if response.status_code == 200:
            server_answer = response.json().get("data", "No data found from server.")
            if server_answer:
                LLM_CACHE[prompt] = server_answer # Save to cache
            return server_answer
        else:
            return f"Server access denied with status {response.status_code}."
    except Exception as e: 
        return f"Connection to the main server failed. Error: {e}"

def ask_ollama_local(prompt):
    print("🧠 Thinking Locally ...")
    try:
        response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
        answer = response['message']['content']
        if answer and len(answer) > 5:
            return answer
    except Exception as e:
        print(f"⚠️ Ollama Skipped (Model offline/busy)")
    return None

# ==========================================
# 1. BACKGROUND ENGINE (QTHREAD) - Aapka Main Loop Yahan Hai
# ==========================================
class JarvisEngineThread(QThread):
    state_changed = pyqtSignal(str)  # 'SLEEP', 'LISTENING', 'THINKING'
    text_updated = pyqtSignal(str)   # Subtitles/Text dikhane ke liye
    # --- NEW SIGNALS FOR GUI CONTROL ---
    animation_speed_changed = pyqtSignal(float)
    animation_color_changed = pyqtSignal(tuple)
    animation_style_changed = pyqtSignal(str)

    def run(self):
        global JARVIS_ACTIVE
        
        self.text_updated.emit("🤖 INITIALIZING JARVIS CORE...")
        self.state_changed.emit("SLEEP")

        # --- WAKE WORD ENGINE INITIALIZATION ---
        # --- NEW: Link signals to the GUI controller ---
        gui_controller.speed_signal.connect(self.animation_speed_changed)
        gui_controller.color_signal.connect(self.animation_color_changed)
        gui_controller.style_signal.connect(self.animation_style_changed)

        if not initialize_wake_word_engine():
            self.text_updated.emit("Error: Vosk Model Failed")
            speak("Critical error: Could not load the offline wake word model. Exiting.")
            return

        with sr.Microphone() as source:
            self.text_updated.emit("🔊 Calibrating microphone...")
            r.adjust_for_ambient_noise(source, duration=1.2)
            r.energy_threshold = 100     
            r.dynamic_energy_threshold = False 
        
        self.text_updated.emit("JARVIS CORE LOADED SUCCESSFULLY")
        speak("Jarvis is online and secured in sleep mode.")

        # --- AAPKA MAIN WHILE LOOP ---
        while True:
            if not JARVIS_ACTIVE:
                self.state_changed.emit("SLEEP")
                self.text_updated.emit("💤 Sleep Mode... (Listening Offline)")
                
                wake_signal = wait_for_wake_word_offline()
                if wake_signal:
                    JARVIS_ACTIVE = True
                    self.text_updated.emit("✅ WAKE WORD DETECTED!")
                    speak("Online and ready, Commander. How can I help you?")
                else:
                    time.sleep(5)
                continue 
                
            self.state_changed.emit("LISTENING")
            self.text_updated.emit("🎙️ Listening... (Boliye Commander)")
            
            user_input = take_command()
            if user_input == "": continue 

            if any(word in user_input for word in ["go to sleep", "sleep", "bye jarvis"]):
                JARVIS_ACTIVE = False
                self.state_changed.emit("SLEEP")
                speak("Going to sleep mode. I will be listening offline.")
                continue

            if any(word in user_input for word in ["exit", "quit"]):
                self.text_updated.emit("System Shutdown")
                speak("Goodbye Commander.")
                break

            self.state_changed.emit("THINKING")
            self.text_updated.emit(f"Processing: '{user_input}'")
            
            # Sequence matching priority
            reply = system_control(user_input) or get_live_info(user_input) or check_local_dictionary(user_input) or solver.handle_query(user_input)
            
            if reply:
                self.text_updated.emit(reply)
                speak(reply)
                continue

            # === MULTI-TIERED HYBRID BRAIN ===
            answer_queue = queue.Queue()
            llm_thread = threading.Thread(
                target=lambda q, p: q.put(get_intelligent_answer(p)), 
                args=(answer_queue, user_input)
            )
            llm_thread.start()
            
            speak("Thinking, one moment Commander...")
            llm_thread.join(timeout=25) 
            
            if llm_thread.is_alive():
                self.text_updated.emit("Timeout Error")
                speak("My apologies, the thinking process took too long and timed out.")
                continue

            try:
                final_answer = answer_queue.get_nowait()
                if final_answer:
                    self.text_updated.emit("Task Completed.")
                    speak(final_answer)
            except queue.Empty:
                self.text_updated.emit("Internal Error")
                speak("I encountered an internal error while processing your request, Commander.")

# ==========================================
# 2. ADVANCED FRAMELESS UI 
# ==========================================
class JarvisUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # UI Setup: Frameless & Transparent
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(100, 100, 400, 400) 
        
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setAlignment(Qt.AlignCenter)

        # 1. Visual GIF Label
        self.gif_label = QLabel(self)
        self.gif_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.gif_label)

        # 2. Text Subtitle Label
        self.text_label = QLabel("Initializing...", self)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setFont(QFont("Consolas", 12, QFont.Bold))
        self.text_label.setStyleSheet("color: #00FFFF; background-color: rgba(0, 0, 0, 150); border-radius: 10px; padding: 5px;")
        
        # Glowing shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 255, 255))
        shadow.setOffset(0, 0)
        self.text_label.setGraphicsEffect(shadow)
        
        self.layout.addWidget(self.text_label)

        # Yahan apne GIFs ke naam dalein (Make sure assets folder me ye exist karein)
        self.gifs = {
            "SLEEP": "assets/sleep.gif",
            "LISTENING": "assets/listening.gif",
            "THINKING": "assets/thinking.gif"
        }
        
        self.current_movie = None
        self.set_ui_state("SLEEP")
        self.old_pos = self.pos()

        # Start Engine
        self.engine_thread = JarvisEngineThread()
        self.engine_thread.state_changed.connect(self.set_ui_state)
        self.engine_thread.text_updated.connect(self.update_text)
        self.engine_thread.start()

    def set_ui_state(self, state):
        if state in self.gifs:
            if self.current_movie:
                self.current_movie.stop()
            self.current_movie = QMovie(self.gifs[state])
            self.gif_label.setMovie(self.current_movie)
            self.current_movie.start()

    def update_text(self, text):
        self.text_label.setText(text)

    # Mouse Events (Drag karne ke liye)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JarvisUI()
    window.show()
    sys.exit(app.exec_())
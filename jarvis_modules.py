import os
import time
import datetime
import re
import subprocess
import pyautogui
import psutil
import smtplib
import urllib.parse
import tkinter as tk
import cv2
import ctypes
import webbrowser
import io
import base64
from PIL import Image
import mss # Faster screenshots
import ollama 
from email.message import EmailMessage

import screen_brightness_control as sbc
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from system_doctor import SystemDoctor, DeepHealProtocol
from system_guardian import SystemGuardian

# These were moved from jarvis_core but are better placed here
import requests
import threading
import sympy
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
from collections import Counter

from scipy import constants
from chempy import balance_stoichiometry, Substance
from periodictable import formula as FormulaParser

# Groq client ko import karna, agar GROQ_API_KEY set hai toh
try:
    from groq import Groq
except ImportError:
    Groq = None


def open_in_chrome(url):
    """Helper function to open URLs in Chrome specifically."""
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
    """Helper function to find and play a song on YouTube."""
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


class HardwareControl:
    """Handles direct hardware interactions like volume, brightness, and power states."""

    def handle_query(self, query, take_command_func, speak_func):
        if "volume" in query or "mute" in query:
            return self.control_volume(query)
        if "brightness" in query:
            return self.control_brightness(query)
        if any(word in query for word in ["lock my laptop", "lock windows", "secure system", "shutdown", "power off laptop", "restart", "reboot"]):
            return self.control_power(query, take_command_func, speak_func)
        return None

    def control_volume(self, query):
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            
            current_level_scalar = volume.GetMasterVolumeLevelScalar()
            current_level_percent = int(current_level_scalar * 100)
            numbers = re.findall(r'\d+', query)
            
            if numbers:
                level = int(numbers[0])
                level = max(0, min(100, level))
                volume.SetMasterVolumeLevelScalar(level / 100.0, None)
                return f"Volume set to {level} percent, Commander."
            elif "up" in query or "increase" in query:
                new_level = min(100, current_level_percent + 10)
                volume.SetMasterVolumeLevelScalar(new_level / 100.0, None)
                return f"Volume increased to {new_level} percent."
            elif "down" in query or "decrease" in query:
                new_level = max(0, current_level_percent - 10)
                volume.SetMasterVolumeLevelScalar(new_level / 100.0, None)
                return f"Volume decreased to {new_level} percent."
            elif "mute" in query:
                volume.SetMute(not volume.GetMute(), None)
                return f"System has been {'muted' if volume.GetMute() else 'unmuted'}."
        except Exception as e:
            return f"Audio hardware control failed: {e}"
        return None

    def _send_windows_toast(self, title, message):
        powershell_script = f'''
        [void] [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms");
        $notification = New-Object System.Windows.Forms.NotifyIcon;
        $notification.Icon = [System.Drawing.SystemIcons]::Information;
        $notification.BalloonTipTitle = "{title}";
        $notification.BalloonTipText = "{message}";
        $notification.Visible = $true;
        $notification.ShowBalloonTip(1500);
        '''
        subprocess.run(["powershell", "-Command", powershell_script], capture_output=True)

    def control_brightness(self, query):
        if any(char.isdigit() for char in query):
            numbers = re.findall(r'\d+', query)
            if numbers:
                level = int(numbers[0])
                level = max(0, min(100, level))
                try:
                    sbc.set_brightness(level)
                    self._send_windows_toast("Jarvis System Control", f"Brightness set to {level}%")
                    return f"Brightness updated to {level} percent, Commander."
                except Exception:
                    return "Hardware synchronization failed."
        elif "up" in query or "increase" in query:
            try:
                current = sbc.get_brightness()[0]
                new_level = min(100, current + 10)
                sbc.set_brightness(new_level)
                self._send_windows_toast("Jarvis System Control", f"Brightness increased to {new_level}%")
                return f"Brightness increased to {new_level} percent."
            except Exception:
                return "Unable to access display hardware."
        elif "down" in query or "decrease" in query:
            try:
                current = sbc.get_brightness()[0]
                new_level = max(0, current - 10)
                sbc.set_brightness(new_level)
                self._send_windows_toast("Jarvis System Control", f"Brightness decreased to {new_level}%")
                return f"Brightness decreased to {new_level} percent."
            except Exception:
                return "Unable to access display hardware."
        return None

    def control_power(self, query, take_command_func, speak_func):
        if "lock my laptop" in query or "lock windows" in query or "secure system" in query:
            speak_func("Securing your main access terminal immediately, Commander.")
            ctypes.windll.user32.LockWorkStation()
            return "Workstation locked successfully."
        elif "shutdown" in query or "power off laptop" in query:
            speak_func("Warning Commander: You are initiating a hard system shutdown. Confirm action by saying Proceed or Abort.")
            confirmation = take_command_func()
            if "proceed" in confirmation or "yes" in confirmation:
                speak_func("Deactivating Jarvis core. Powering down system subsystems in 5 seconds. Goodbye, sir.")
                subprocess.run(["shutdown", "/s", "/t", "5"], check=False)
                return "Shutdown protocol armed."
            else:
                return "Shutdown sequence intercepted and canceled."
        elif "restart" in query or "reboot" in query:
            speak_func("Confirm system reboot request, sir.")
            confirmation = take_command_func()
            if "proceed" in confirmation or "yes" in confirmation:
                speak_func("Rebooting main architecture. System offline shortly.")
                subprocess.run(["shutdown", "/r", "/t", "5"], check=False)
                return "Reboot sequence armed."
            else:
                return "Reboot aborted."
        return None

class ApplicationControl:
    """Handles opening, closing, installing, and uninstalling applications."""
    # Keep a small map for common aliases or quick access
    APP_MAP = {
        "notepad": "notepad.exe",
        "chrome": "chrome.exe",
        "calculator": "calc.exe",
        "word": "winword.exe",
        "paint": "mspaint.exe",
        "edge": "msedge.exe",
        "spotify": "spotify.exe" # Assuming spotify is in PATH
    }

    def __init__(self, my_email, my_email_password):
        self.my_email = my_email
        self.my_email_password = my_email_password
        # Cache for found app paths to speed up subsequent requests
        self._app_path_cache = {}
        # List to keep track of background installation threads
        self.installation_threads = []

    def handle_query(self, query, take_command_func, speak_func):
        # Order is important: install/uninstall should be checked before open/close
        if "installation status" in query or "check installations" in query or "background tasks" in query:
            return self.check_installation_status(speak_func)

        if "install" in query or "download" in query:
            return self.manage_installation(query, speak_func, action="install")
        
        if "uninstall" in query or "remove" in query or "delete" in query:
            # Add a guard to not confuse with "delete file"
            if "file" not in query and "folder" not in query:
                return self.manage_installation(query, speak_func, action="uninstall")

        if "open" in query or "launch" in query:
            return self.open_app(query, speak_func)

        if "close" in query or "terminate" in query:
            # Use the existing robust process killer
            return self.close_app(query, speak_func)

        # Keep the other functionalities
        if "play" in query and "youtube" in query:
            song = query.replace("play", "").replace("on youtube", "").replace("youtube pe", "").replace("song", "").strip()
            if song: return play_on_youtube(song)
        if "send whatsapp" in query or "whatsapp message" in query:
            return self.send_whatsapp(query, take_command_func, speak_func)
        if "send email" in query or "email send" in query:
            return self.send_email(query, take_command_func, speak_func)
            
        return None

    def _find_app_path(self, app_name):
        """Advanced search for an application executable or shortcut."""
        app_name = app_name.lower()
        if app_name in self._app_path_cache:
            return self._app_path_cache[app_name]

        # Search in common Start Menu locations
        search_paths = [
            os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "Microsoft\\Windows\\Start Menu\\Programs"),
            os.path.join(os.environ.get("APPDATA"), "Microsoft\\Windows\\Start Menu\\Programs")
        ]
        
        # Also check common installation folders
        program_files_paths = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)")
        ]
        for p_path in program_files_paths:
            if p_path and os.path.exists(p_path):
                search_paths.append(p_path)

        for path in search_paths:
            for root, dirs, files in os.walk(path):
                for file in files:
                    # Match if app_name is in the filename (case-insensitive)
                    if app_name in file.lower() and file.lower().endswith(('.exe', '.lnk')):
                        # Prioritize exact matches
                        file_base = os.path.splitext(file)[0].lower()
                        if file_base == app_name:
                            found_path = os.path.join(root, file)
                            self._app_path_cache[app_name] = found_path
                            return found_path
        return None

    def open_app(self, query, speak_func):
        """Opens any application by searching for it."""
        app_name = query.replace("open", "").replace("launch", "").strip()
        
        # 1. Check the quick map first
        if app_name in self.APP_MAP:
            try:
                os.startfile(self.APP_MAP[app_name])
                return f"Opening {app_name.title()}."
            except Exception:
                pass # Fall through to deep search

        # 2. If not in map, perform advanced search
        speak_func(f"Searching for {app_name} in system applications...")
        app_path = self._find_app_path(app_name)
        
        if app_path:
            try:
                os.startfile(app_path)
                return f"Found and opening {app_name.title()}."
            except Exception as e:
                return f"Found {app_name} but failed to open it. Error: {e}"
        else:
            # 3. As a last resort, try to run it directly, it might be in PATH
            try:
                # Use Popen to not block Jarvis
                subprocess.Popen([app_name])
                return f"Attempting to launch {app_name} from system path."
            except Exception:
                return f"Sorry Commander, I could not find any application named '{app_name}' on your system."

    def close_app(self, query, speak_func):
        """Closes an application by terminating its process."""
        app_name = query.replace("close", "").replace("terminate", "").strip()
        # Remove .exe if user says it
        if app_name.endswith(".exe"):
            app_name = app_name[:-4]

        speak_func(f"Attempting to terminate all processes for {app_name}, Commander.")
        terminated_count = 0
        
        # Find the executable name from our map if it's an alias
        command_name = self.APP_MAP.get(app_name, app_name)
        
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                # Match against the app name or the command name
                if app_name.lower() in proc.info['name'].lower() or command_name.lower() in proc.info['name'].lower():
                    proc.kill()
                    terminated_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        if terminated_count > 0:
            return f"Successfully terminated {terminated_count} instance(s) of {app_name}."
        else:
            return f"Could not find any active process for {app_name} to close."

    def check_installation_status(self, speak_func):
        """Checks and reports the status of ongoing background installations."""
        # Clean up finished threads first
        self.installation_threads = [t_info for t_info in self.installation_threads if t_info['thread'].is_alive()]

        if not self.installation_threads:
            return "There are no ongoing installations, Commander."

        count = len(self.installation_threads)
        plural_task = "task is" if count == 1 else "tasks are"
        speak_func(f"Commander, {count} background {plural_task} currently running.")
        
        for t_info in self.installation_threads:
            app_name = t_info['app_name']
            action = t_info['action']
            elapsed_time = time.time() - t_info['start_time']
            speak_func(f"Task: {action.capitalize()} {app_name}. Running for {int(elapsed_time)} seconds.")
            
        return "That is the status of all background operations."

    def manage_installation(self, query, speak_func, action="install"):
        """Starts an installation/uninstallation in a background thread to keep Jarvis responsive."""
        app_name = query.replace(action, "").replace("download", "").replace("remove", "").replace("delete", "").strip()
        
        if not app_name:
            return f"Please specify which application to {action}, Commander."

        # Clean up any finished threads from the list to prevent memory bloat
        self.installation_threads = [t_info for t_info in self.installation_threads if t_info['thread'].is_alive()]

        # Create and start the background worker thread
        worker_thread = threading.Thread(
            target=self._winget_worker,
            args=(app_name, action, speak_func),
            daemon=True  # Ensures thread exits when main program exits
        )
        
        # Store detailed info about the thread
        thread_info = {'thread': worker_thread, 'app_name': app_name, 'action': action, 'start_time': time.time()}
        self.installation_threads.append(thread_info)
        worker_thread.start()

        return f"The {action} process for {app_name} has been initiated in the background. I will report back upon completion."

    def _winget_worker(self, app_name, action, speak_func):
        """
        This is the heart of the non-blocking installation. It runs in a separate thread,
        executes the command, and uses the speak_func to report the final result.
        """
        command = [
            "winget", action, "--name", app_name,
            "--accept-source-agreements", "--accept-package-agreements", "--silent"
        ]
        
        try:
            process = subprocess.run(
                command, capture_output=True, text=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            stdout_lower = process.stdout.lower()
            stderr_lower = process.stderr.lower()
            error_output = stdout_lower + stderr_lower
            
            if process.returncode == 0 and (("successfully installed" in stdout_lower) or ("successfully uninstalled" in stdout_lower)):
                speak_func(f"Commander, the {action} of {app_name} has completed successfully.")
            elif "no package found matching input criteria" in error_output:
                speak_func(f"Commander, I could not find a package named '{app_name}'. I recommend searching for the application first.")
            elif "installer hash mismatch" in error_output:
                speak_func(f"A critical security warning, Commander. The installer for {app_name} has a hash mismatch. This is a potential security risk, so I have aborted the {action}.")
            elif "0x80070005" in error_output or "access is denied" in error_output or "run as an administrator" in error_output:
                speak_func(f"Commander, the {action} failed due to insufficient permissions. To solve this, please restart me with administrator privileges.")
            elif "another installation is already in progress" in error_output:
                speak_func(f"Commander, the system reports that another installation is already in progress. Please wait for it to finish or try again later.")
            else:
                print(f"Winget Error Stderr: {process.stderr}")
                print(f"Winget Error Stdout: {process.stdout}")
                speak_func(f"Commander, the {action} of {app_name} failed for an unknown reason. I have logged the error details to the console for your review.")

        except FileNotFoundError:
            speak_func("Critical error: Windows Package Manager (winget) was not found on your system. This feature is unavailable.")
        except Exception as e:
            speak_func(f"An unexpected error occurred during the {action} process: {str(e)}")

    def send_whatsapp(self, query, take_command_func, speak_func):
        speak_func("Commander, please specify the 10-digit phone number.")
        phone_raw = take_command_func()
        phone = "".join(re.findall(r'\d+', phone_raw))
        
        if len(phone) < 10:
            return "Invalid phone number sequence. Aborting protocol."
        if len(phone) == 10:
            phone = "91" + phone
            
        speak_func("What is the payload message, sir?")
        msg = take_command_func()
        
        if not msg:
            return "Message payload empty. Operation aborted."
            
        encoded_msg = urllib.parse.quote(msg)
        whatsapp_url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_msg}"
        
        open_in_chrome(whatsapp_url)
        speak_func("Initializing WhatsApp Web interface. Deploying message in 12 seconds.")
        
        time.sleep(12) 
        pyautogui.press('enter')
        return "Message deployed successfully, Commander."

    def send_email(self, query, take_command_func, speak_func):
        speak_func("Sir, please state the receiver's email address.")
        receiver_raw = take_command_func()
        receiver = receiver_raw.replace(" at the rate ", "@").replace(" at ", "@").replace(" dot ", ".").replace(" ", "").strip()

        if "@" not in receiver or "." not in receiver:
            return f"Invalid email format parsed: '{receiver}'. Protocol aborted."

        speak_func("What is the subject of the email, Commander?")
        subject = take_command_func()

        speak_func("What should be the main payload message?")
        body = take_command_func()

        if not body:
            return "Email body cannot be empty. Protocol halted."

        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = self.my_email
            msg['To'] = receiver
            msg.set_content(body)

            speak_func("Connecting to secure SMTP server...")
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(self.my_email, self.my_email_password)
                smtp.send_message(msg)
            
            return f"Email successfully transmitted to {receiver}."
        except Exception as e:
            print(f"⚠️ SMTP Error: {e}")
            return "Failed to send email. Please verify SMTP credentials or network state."

class SystemInteraction:
    """Handles general OS interactions like typing, window management, and file operations."""

    def handle_query(self, query, take_command_func, speak_func):
        if "type" in query or "write" in query:
            return self.fast_typing(query, take_command_func, speak_func)
        if any(word in query for word in ["switch window", "change window", "close tab", "new tab", "minimize", "go to desktop", "screenshot", "capture screen", "maximize", "restore", "active window"]):
            return self.manage_workspace(query, speak_func)
        if "clipboard" in query or "copied text" in query:
            return self.manage_clipboard(query, speak_func)
        if "kill" in query or "force close" in query or "terminate" in query:
            return self.kill_process(query)
        if "find file" in query or "search file" in query or "locate file" in query:
            return self.find_file(query, speak_func)
        if any(word in query for word in ["pause music", "play music", "resume music", "next song", "previous song", "change track"]):
            return self.control_media(query)
        if "open camera" in query or "activate vision" in query or "jarvis eyes" in query:
            return self.activate_vision(speak_func)
        return None

    def fast_typing(self, query, take_command_func, speak_func):
        if "in" in query:
            parts = query.split("in")
            text = parts[0].replace("type", "").replace("write", "").strip()
            app_choice = parts[1].strip()
            speak_func(f"Typing in {app_choice}.")
        else:
            speak_func("Kya type karna hai?")
            text = take_command_func()
            speak_func("Kahan?")
            app_choice = take_command_func()

        app_exe = "notepad.exe" if "notepad" in app_choice else "chrome.exe"
        try:
            os.startfile(app_exe)
            time.sleep(0.8) 
            pyautogui.write(text, interval=0.01) 
            pyautogui.press("enter")
            return "Done, Commander."
        except Exception:
            return f"Could not start {app_choice}."

    def manage_workspace(self, query, speak_func):
        if "switch window" in query or "change window" in query:
            pyautogui.hotkey('alt', 'tab')
            return "Switched window, Commander."
        elif "close tab" in query:
            pyautogui.hotkey('ctrl', 'w')
            return "Closed current tab."
        elif "new tab" in query:
            pyautogui.hotkey('ctrl', 't')
            return "Opened new tab."
        elif "minimize" in query or "go to desktop" in query:
            pyautogui.hotkey('win', 'd')
            return "Minimizing all windows."
        elif "maximize" in query:
            try:
                window = pyautogui.getActiveWindow()
                if window:
                    window.maximize()
                    return "Window maximized, Commander."
                return "No active window found to maximize."
            except Exception as e:
                return f"Could not maximize window: {e}"
        elif "restore" in query or "normal size" in query:
            try:
                window = pyautogui.getActiveWindow()
                if window:
                    window.restore()
                    return "Window restored to normal size."
                return "No active window found to restore."
            except Exception as e:
                return f"Could not restore window: {e}"
        elif "what is this window" in query or "active window title" in query or "window name" in query:
            try:
                window = pyautogui.getActiveWindow()
                if window and window.title:
                    title = window.title
                    speak_func(f"The active window is titled: {title}")
                    return "Title reported."
                return "Could not identify the active window's title."
            except Exception as e:
                return f"Could not get window title: {e}"
        elif "screenshot" in query or "capture screen" in query:
            if not os.path.exists("Jarvis_Screenshots"):
                os.makedirs("Jarvis_Screenshots")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            ss_path = f"Jarvis_Screenshots/Screenshot_{timestamp}.png"
            pyautogui.screenshot(ss_path)
            return f"Screenshot captured and saved in Jarvis Screenshots folder."
        return None

    def manage_clipboard(self, query, speak_func):
        try:
            root = tk.Tk()
            root.withdraw() 
            clipboard_data = root.clipboard_get()
            
            if not clipboard_data.strip():
                return "Clipboard is currently empty, Commander."
                
            if "read" in query or "speak" in query or "tell me" in query:
                speak_func("Current clipboard content is:")
                return clipboard_data
            elif "save" in query or "note" in query:
                notes_folder = "Jarvis_Notes"
                if not os.path.exists(notes_folder):
                    os.makedirs(notes_folder)
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
                note_file = f"{notes_folder}/Note_{timestamp}.txt"
                with open(note_file, "w", encoding="utf-8") as file:
                    file.write(clipboard_data)
                return f"Data successfully secured in Jarvis Notes as Note_{timestamp}.txt."
        except tk.TclError:
            return "Protocol failed. Clipboard is either empty or does not contain readable text."
        except Exception as e:
            return f"An unexpected error occurred with the clipboard protocol: {e}"
        return None

    def kill_process(self, query):
        target_app = query.replace("kill", "").replace("force close", "").replace("terminate", "").replace("process", "").replace("app", "").strip()
        if not target_app:
            return "Please specify the application name to terminate, Commander."
        terminated_count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if target_app.lower() in proc.info['name'].lower():
                    proc.kill()
                    terminated_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if terminated_count > 0:
            return f"Successfully terminated {terminated_count} instances of {target_app}."
        else:
            return f"Could not find any active process named {target_app}."

    def find_file(self, query, speak_func):
        file_name = query.replace("find file", "").replace("search file", "").replace("locate file", "").strip()
        if not file_name:
            return "Please specify the file name to search, Commander."
        speak_func(f"Initiating deep system scan for '{file_name}'. This might take a few moments.")
        search_path = os.path.expanduser('~')
        found_path = None
        for root, dirs, files in os.walk(search_path):
            if found_path: break
            for file in files:
                if file_name.lower() in file.lower():
                    found_path = os.path.join(root, file)
                    break
        if found_path:
            os.system(f'explorer /select,"{found_path}"')
            return f"File located successfully. Opening the directory."
        else:
            return f"Scan complete. No file named '{file_name}' was found in the primary directories."

    def control_media(self, query):
        try:
            if "pause" in query or "stop" in query:
                pyautogui.press("playpause")
                return "Playback suspended."
            elif "play" in query or "resume" in query:
                pyautogui.press("playpause")
                return "Resuming media playback."
            elif "next" in query or "skip" in query:
                pyautogui.press("nexttrack")
                return "Skipping to the next track sequence."
            elif "previous" in query or "back" in query:
                pyautogui.press("prevtrack")
                return "Reverting to previous track."
        except Exception as e:
            return f"Media control command failed. Error: {e}"
        return None

    def activate_vision(self, speak_func):
        speak_func("Activating primary visual sensors, sir. Press 'Q' on the video window to terminate the feed.")
        cap = cv2.VideoCapture(0) 
        while True:
            ret, frame = cap.read()
            if not ret:
                speak_func("Error accessing visual sensors.")
                break
            cv2.putText(frame, "JARVIS VISION CORE - ACTIVE", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, "TARGET LOCKED - S. SUDIPTO", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.imshow("Jarvis Visual Feed", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cap.release()
        cv2.destroyAllWindows()
        return "Visual sensors deactivated and secured."

class SystemMaintenance:
    """Handles system diagnostics, repairs, and health checks."""

    def __init__(self):
        self.doctor = SystemDoctor()
        self.healer = DeepHealProtocol()
        self.guardian = SystemGuardian()

    def handle_query(self, query, speak_func):
        if any(word in query for word in ["fix my laptop", "optimize system", "clean junk", "system diagnosis"]):
            speak_func("Initiating deep system scan and optimization protocol. Please wait...")
            return self.doctor.run_full_diagnosis()
        if "fix network" in query or "internet is slow" in query:
            speak_func("Resetting network adapters and flushing DNS.")
            return self.doctor.fix_network_glitch()
        if "initiate deep heal" in query or "fix everything" in query or "repair system" in query:
            speak_func("Warning Commander. Initiating Deep Heal Engine Protocol. This will clear system registers, reconstruct network nodes, and scan system files in the background architecture layer. Proceeding now.")
            return self.healer.deploy_deep_heal_sequence()
        
        deep_control_result = self.doctor.execute_deep_control(query)
        if deep_control_result:
            return deep_control_result

        if "god mode" in query or "open all settings" in query:
            speak_func("Accessing the master control panel, Commander.")
            os.system('explorer shell:::{ED7BA470-8E54-465E-825C-99712043E01C}')
            return "God mode folder deployed."
        if "system health" in query or "how is my laptop" in query:
            report = self.guardian.check_system_health()
            speak_func(report["message"])
            if report.get("status") == "CRITICAL":
                speak_func("Checking which applications are causing this load...")
                hogs = self.guardian.get_top_resource_hogs(track_by="memory", limit=2)
                for app in hogs:
                    speak_func(f"Application {app['name']} is consuming heavy resources with process ID {app['pid']}.")
            return "Diagnosis reported."
        if "internet speed" in query or "check network speed" in query:
            speak_func("Testing network bandwidth, please hold on...")
            return self.guardian.get_network_speed()
        return None

class MemoryManager:
    """Handles long-term memory storage and retrieval."""

    def handle_query(self, query, take_command_func, speak_func):
        if "remember that" in query or "yaad rakho" in query:
            return self.remember(query, speak_func)
        if "what do you remember" in query or "kya yaad hai" in query or "read memory" in query:
            return self.recall(speak_func)
        if "clear memory" in query or "format memory" in query or "forget everything" in query:
            return self.clear(take_command_func, speak_func)
        return None

    def remember(self, query, speak_func):
        memory_msg = query.replace("remember that", "").replace("yaad rakho ki", "").replace("yaad rakho", "").strip()
        if memory_msg:
            speak_func(f"Got it, Commander. I am storing this in my core memory: {memory_msg}")
            with open("Jarvis_Memory.txt", "a", encoding="utf-8") as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                f.write(f"[{timestamp}] - {memory_msg}\n")
            return "Data successfully logged into memory banks."
        else:
            return "What exactly should I remember, sir?"

    def recall(self, speak_func):
        try:
            with open("Jarvis_Memory.txt", "r", encoding="utf-8") as f:
                memories = f.readlines()
            if memories:
                speak_func("Commander, here is what I have in my memory banks:")
                for memory in memories:
                    clean_memory = memory.split(" - ")[-1].strip()
                    speak_func(clean_memory)
                    time.sleep(0.5)
                return "That concludes my memory logs, sir."
            else:
                return "My memory banks are currently empty."
        except FileNotFoundError:
            return "My memory banks are currently empty, sir."

    def clear(self, take_command_func, speak_func):
        speak_func("Warning: You are about to format my memory core. Say 'proceed' to confirm or 'cancel' to abort.")
        confirm = take_command_func()
        if "proceed" in confirm or "yes" in confirm:
            open("Jarvis_Memory.txt", "w").close() 
            return "Memory core formatted successfully. All previous logs have been erased."
        else:
            return "Memory format protocol aborted. Data is safe."

class AdvancedSolver:
    """
    Handles complex mathematical, physical, and chemical problems using symbolic computation.
    This class integrates a vast knowledge base of Physics, Mathematics, and Chemistry.
    """
    def __init__(self):
        # --- Symbol Definition for All Scientific Domains ---
        F, m, a, E, c, v, u, t, s, W, d, P, KE, PE, g, h, V_elec, I_elec, R_elec, p_mom, B = sympy.symbols('F m a E c v u t s W d P KE PE g h V_elec I_elec R_elec p_mom B')
        f_friction, mu, N, tau, r, I, omega, L_ang, G, m1, m2 = sympy.symbols('f_friction mu N tau r I omega L_ang G m1 m2')
        rho, V_vol, P_press, A_area, P_gas, V_gas, n_moles, R_gas, T_temp = sympy.symbols('rho V_vol P_press A_area P_gas V_gas n_moles R_gas T_temp')
        delta_Q, delta_U, delta_W, T_period, L_len, f_freq, lambda_wl = sympy.symbols('delta_Q delta_U delta_W T_period L_len f_freq lambda_wl')
        epsilon_0, q, q1, q2, E_field, f_focal, v_image, u_object, mu_ref, i_angle, r_angle = sympy.symbols('epsilon_0 q q1 q2 E_field f_focal v_image u_object mu_ref i_angle r_angle')
        h_planck, nu_freq = sympy.symbols('h_planck nu_freq')
        self.x, self.y, self.z = sympy.symbols('x y z')

        # --- 1. Physics Formula Knowledge Base ---
        self.physics_formulas = {
            'force': {'eq': sympy.Eq(F, m * a), 'vars': {'mass': m, 'acceleration': a, 'force': F}},
            'momentum': {'eq': sympy.Eq(p_mom, m * v), 'vars': {'momentum': p_mom, 'mass': m, 'velocity': v}},
            'friction': {'eq': sympy.Eq(f_friction, mu * N), 'vars': {'friction_force': f_friction, 'coefficient_of_friction': mu, 'normal_force': N}},
            'equation of motion velocity': {'eq': sympy.Eq(v, u + a * t), 'vars': {'final_velocity': v, 'initial_velocity': u, 'acceleration': a, 'time': t}},
            'equation of motion displacement': {'eq': sympy.Eq(s, u*t + 0.5*a*t**2), 'vars': {'displacement': s, 'initial_velocity': u, 'acceleration': a, 'time': t}},
            'equation of motion final velocity': {'eq': sympy.Eq(v**2, u**2 + 2*a*s), 'vars': {'final_velocity': v, 'initial_velocity': u, 'acceleration': a, 'displacement': s}},
            'work': {'eq': sympy.Eq(W, F * d), 'vars': {'work': W, 'force': F, 'distance': d}},
            'power': {'eq': sympy.Eq(P, W / t), 'vars': {'power': P, 'work': W, 'time': t}},
            'kinetic energy': {'eq': sympy.Eq(KE, 0.5 * m * v**2), 'vars': {'kinetic_energy': KE, 'mass': m, 'velocity': v}},
            'potential energy': {'eq': sympy.Eq(PE, m * g * h), 'vars': {'potential_energy': PE, 'mass': m, 'gravity': g, 'height': h}},
            'torque': {'eq': sympy.Eq(tau, r * F), 'vars': {'torque': tau, 'radius': r, 'force': F}},
            'angular momentum': {'eq': sympy.Eq(L_ang, I * omega), 'vars': {'angular_momentum': L_ang, 'moment_of_inertia': I, 'angular_velocity': omega}},
            'gravitational force': {'eq': sympy.Eq(F, (G * m1 * m2) / r**2), 'vars': {'force': F, 'gravitational_constant': G, 'mass1': m1, 'mass2': m2, 'distance': r}},
            'acceleration due to gravity': {'eq': sympy.Eq(g, (G * m) / r**2), 'vars': {'acceleration_due_to_gravity': g, 'gravitational_constant': G, 'mass_of_planet': m, 'radius_of_planet': r}},
            'density': {'eq': sympy.Eq(rho, m / V_vol), 'vars': {'density': rho, 'mass': m, 'volume': V_vol}},
            'pressure': {'eq': sympy.Eq(P_press, F / A_area), 'vars': {'pressure': P_press, 'force': F, 'area': A_area}},
            'ideal gas law': {'eq': sympy.Eq(P_gas * V_gas, n_moles * R_gas * T_temp), 'vars': {'pressure': P_gas, 'volume': V_gas, 'moles': n_moles, 'gas_constant': R_gas, 'temperature': T_temp}},
            'first law of thermodynamics': {'eq': sympy.Eq(delta_Q, delta_U + delta_W), 'vars': {'heat_added': delta_Q, 'internal_energy_change': delta_U, 'work_done': delta_W}},
            'pendulum time period': {'eq': sympy.Eq(T_period, 2 * sympy.pi * sympy.sqrt(L_len / g)), 'vars': {'time_period': T_period, 'length': L_len, 'gravity': g}},
            'wave speed': {'eq': sympy.Eq(v, f_freq * lambda_wl), 'vars': {'wave_speed': v, 'frequency': f_freq, 'wavelength': lambda_wl}},
            'coulombs law': {'eq': sympy.Eq(F, (1 / (4 * sympy.pi * epsilon_0)) * (q1 * q2) / r**2), 'vars': {'force': F, 'permittivity': epsilon_0, 'charge1': q1, 'charge2': q2, 'distance': r}},
            'electric field': {'eq': sympy.Eq(E_field, F / q), 'vars': {'electric_field': E_field, 'force': F, 'charge': q}},
            "ohms law": {'eq': sympy.Eq(V_elec, I_elec * R_elec), 'vars': {'voltage': V_elec, 'current': I_elec, 'resistance': R_elec}},
            'electric power': {'eq': sympy.Eq(P, V_elec * I_elec), 'vars': {'power': P, 'voltage': V_elec, 'current': I_elec}},
            'magnetic force': {'eq': sympy.Eq(F, q * v * B), 'vars': {'force': F, 'charge': q, 'velocity': v, 'magnetic_field': B}},
            'mirror formula': {'eq': sympy.Eq(1/f_focal, 1/v_image + 1/u_object), 'vars': {'focal_length': f_focal, 'image_distance': v_image, 'object_distance': u_object}},
            'lens formula': {'eq': sympy.Eq(1/f_focal, 1/v_image - 1/u_object), 'vars': {'focal_length': f_focal, 'image_distance': v_image, 'object_distance': u_object}},
            'snells law': {'eq': sympy.Eq(mu_ref, sympy.sin(i_angle) / sympy.sin(r_angle)), 'vars': {'refractive_index': mu_ref, 'angle_of_incidence': i_angle, 'angle_of_refraction': r_angle}},
            'energy': {'eq': sympy.Eq(E, m * c**2), 'vars': {'mass': m, 'energy': E}},
            'photon energy': {'eq': sympy.Eq(E, h_planck * nu_freq), 'vars': {'energy': E, 'plancks_constant': h_planck, 'frequency': nu_freq}},
            'de broglie wavelength': {'eq': sympy.Eq(lambda_wl, h_planck / p_mom), 'vars': {'wavelength': lambda_wl, 'plancks_constant': h_planck, 'momentum': p_mom}},
        }
        self.constants = {
            'c': constants.c,
            'g': constants.g,
            'G': constants.G,
            'h': constants.h,
            'R': constants.R,
            'epsilon_0': constants.epsilon_0
        }

        # --- 2. Mathematics Glossary Knowledge Base ---
        self.math_definitions = {
            "arithmetic": "Arithmetic is the study of numbers and basic operations like addition, subtraction, multiplication, and division.",
            "algebra": "Algebra uses letters and symbols, called variables, to represent numbers and formulate rules in equations.",
            "calculus": "Calculus is the mathematical study of continuous change, exploring concepts like limits, derivatives, and integrals.",
            "geometry": "Geometry is the field concerned with questions of shape, size, and the relative position of figures in space.",
            "probability": "Probability measures the likelihood of an event occurring, quantified as a number between 0 and 1.",
            "statistics": "Statistics is the discipline that concerns the collection, analysis, interpretation, and presentation of data.",
            "trigonometry": "Trigonometry is the study of relationships between the angles and side lengths of triangles, using functions like sine, cosine, and tangent.",
            "binomial": "A binomial is an algebraic expression containing exactly two terms.",
            "diameter": "A diameter is a straight line passing through the center of a circle, connecting two points on the circumference.",
            "exponent": "An exponent is a notation indicating how many times a base number is to be multiplied by itself.",
            "function": "A function is a relation where each input has exactly one output.",
            "hypotenuse": "The hypotenuse is the longest side of a right-angled triangle, opposite the right angle.",
            "integer": "An integer is any whole number, including positive, negative, and zero.",
            "limit": "A limit is the value that a function approaches as the input approaches some specific value.",
            "matrix": "A matrix is a rectangular array of numbers, symbols, or expressions, arranged in rows and columns.",
            "number line": "A number line is a visual representation of numbers on a straight line.",
            "octahedron": "An octahedron is a polyhedron with eight faces.",
            "polynomial": "A polynomial is an expression of variables and coefficients, involving only addition, subtraction, multiplication, and non-negative integer exponents.",
            "quadratic equation": "A quadratic equation is an equation of the form ax² + bx + c = 0, typically solved using the quadratic formula.",
            "rational number": "A rational number is any number that can be expressed as a fraction p/q of two integers.",
            "variable": "A variable is a symbol, usually a letter like x or y, used to represent an unspecified number.",
            "whole numbers": "Whole numbers are all non-negative integers (0, 1, 2, 3, and so on).",
            "y-intercept": "The y-intercept is the point where a line or curve crosses the graph's y-axis."
        }

    # --- MASTER ROUTER ---
    def handle_query(self, query):
        """Main router to decide which function to call based on the query."""
        query = query.lower()

        # Priority 1: Definitions
        if "define" in query or "what is" in query or "what are" in query:
            for concept in self.math_definitions:
                if concept in query:
                    return self.math_definitions[concept]

        # Priority 2: Scientific Calculations (Physics, Chemistry)
        if any(k in query for k in ["balance", "molar mass", "molecular weight", "stoichiometry"]):
            return self._solve_chemistry(query)
        if any(k in query for k in self.physics_formulas.keys()) and "calculate" in query:
            return self._solve_physics(query)
        if "convert" in query and ("to" in query or "into" in query):
            return self._convert_units(query)

        # Priority 3: Advanced Mathematics
        if "statistics of" in query:
            data_str = query.split("statistics of")[-1]
            try:
                data_list = [float(i) for i in re.findall(r'-?\d+\.?\d*', data_str)]
                return str(self.calculate_statistics(data_list)) if data_list else "Could not parse data for statistics."
            except: return "Invalid data for statistics."
        
        trig_match = re.search(r'(sin|cos|tan|sine|cosine|tangent) of (\d+\.?\d*)', query)
        if trig_match:
            return self.calculate_trigonometry(trig_match.group(1), float(trig_match.group(2)))

        calc_match = re.search(r'(derivative|integral|limit) of (.*)', query)
        if calc_match:
            op_type = calc_match.group(1)
            expr_str = calc_match.group(2).split(" with respect to ")[0]
            return self.calculate_calculus(expr_str, op_type=op_type)

        quad_match = re.search(r'solve quadratic with a as (-?\d+\.?\d*), b as (-?\d+\.?\d*), and c as (-?\d+\.?\d*)', query)
        if quad_match:
            a, b, c = map(float, quad_match.groups())
            return str(self.solve_quadratic(a, b, c))

        if "solve" in query and "=" in query:
            return self.solve_algebra(query.split("solve")[-1].strip())

        num_match = re.search(r'classify the number (-?\d+\.?\d*)', query)
        if num_match:
            return str(self.classify_and_simplify_number(num_match.group(1)))

        # Priority 4: Basic Arithmetic (Fallback)
        if any(word in query for word in ["calculate", "what is"]) and re.search(r'\d', query):
            expr_str = query.replace("calculate", "").replace("what is", "").strip()
            if not any(k in expr_str for k in ["statistics", "trigonometry", "calculus", "solve"]):
                 return str(self.calculate_arithmetic(expr_str))

        return None

class GUIControl(QObject):
    """
    Handles voice commands related to the GUI animation.
    It parses the command and emits signals that the GUI can connect to.
    """
    # Signals that will be emitted to the GUI
    speed_signal = pyqtSignal(float)
    color_signal = pyqtSignal(tuple)
    style_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.color_map = {
            "red": (1.0, 0.2, 0.2),
            "green": (0.2, 1.0, 0.2),
            "blue": (0.2, 0.5, 1.0),
            "cyan": (0.0, 0.9, 1.0),
            "white": (1.0, 1.0, 1.0),
            "yellow": (1.0, 1.0, 0.0),
            "purple": (0.8, 0.4, 1.0),
            "original": (0.0, 0.9, 1.0) # Default color
        }

    def handle_query(self, query):
        query = query.lower()

        # --- Speed Control ---
        if "go faster" in query or "increase speed" in query:
            self.speed_signal.emit(2.0) # Double speed
            return "Animation speed increased, Commander."
        if "slow down" in query or "decrease speed" in query:
            self.speed_signal.emit(0.5) # Half speed
            return "Animation speed decreased."
        if "normal speed" in query or "reset speed" in query:
            self.speed_signal.emit(1.0) # Normal speed
            return "Animation speed reset to normal."

        # --- Color Control ---
        if "change color to" in query:
            for color_name, color_values in self.color_map.items():
                if color_name in query:
                    self.color_signal.emit(color_values + (0.8,)) # Add alpha
                    return f"Core color matrix updated to {color_name}."
            return "Sorry, I don't recognize that color."

        # --- Style Control ---
        if "search mode" in query or "data indexing" in query:
            self.style_signal.emit("SEARCH")
            return "Engaging data indexing kinetic protocols."
        if "speak mode" in query or "vocal matrix" in query:
            self.style_signal.emit("SPEAK")
            return "Initializing vocal matrix phase rotation."
        if "idle mode" in query or "protocol standby" in query or "normal mode" in query:
            self.style_signal.emit("IDLE")
            return "Reverting to standard idle protocols."


        return None # Command not handled

class ScreenVisionControl:
    """
    Advanced Screen Analysis Module: Screen capture karke AI models (Groq or Ollama) 
    ke zariye content aur context analyze karta hai.
    """
    def __init__(self):
        # Groq Client initialize karna environment variable se
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.analysis_thread = None
        if self.groq_api_key and Groq:
            self.groq_client = Groq(api_key=self.groq_api_key)
        else:
            self.groq_client = None

    def handle_query(self, query, speak_func):
        # Keywords check karna screen analysis ke liye
        keywords = ["look at my screen", "analyze screen", "screen par kya hai", "see my screen", "read my screen"]
        if any(kw in query for kw in keywords):
            # User ka custom prompt extract karna (e.g., "Look at my screen and find the error")
            prompt = query
            for kw in keywords:
                prompt = prompt.replace(kw, "")
            prompt = prompt.strip()
            
            # Agar user ne koi specific sawal nahi pucha, toh default overview prompt dena
            if not prompt:
                prompt = "Please look at my screen and describe what you see, including any active windows, text, or errors in detail."
            
            speak_func("Scanning the visual terminal and initializing vision protocols, Commander...") # Check if a previous analysis is still running
            if self.analysis_thread and self.analysis_thread.is_alive():
                return "A screen analysis is already in progress, Commander. Please wait for it to complete."

            # Run the heavy analysis in a background thread
            self.analysis_thread = threading.Thread(
                target=self.capture_and_analyze,
                args=(prompt, speak_func),
                daemon=True
            )
            self.analysis_thread.start()
            
            return "Analysis initiated. I will report back with my findings shortly."
            
        return None

    def capture_and_analyze(self, prompt, speak_func):
        try:
            # 1. Silently take a screenshot
            # screenshot = pyautogui.screenshot() # This is slower, mss is better.
            
            # 2. Memory optimize karne ke liye image ko direct bytes me convert karna (No Disk Writing)
            # 1. Use MSS for faster screen capture
            with mss.mss() as sct:
                sct_img = sct.grab(sct.monitors[1])
                screenshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            # 2. Pre-process and optimize image
            screenshot.thumbnail((1024, 1024)) # Resize for faster processing
            buffered = io.BytesIO()
            screenshot.save(buffered, format="JPEG", quality=75) # 75% quality balances bandwidth and speed
            img_bytes = buffered.getvalue()
            
            # 3. PRIORITY 1: Groq Cloud Vision (Extremely Fast and Highly Smart)
            if self.groq_client:
                print("🌐 [VISION ENGINE] Deploying Groq Cloud Vision Model...")
                base64_image = base64.b64encode(img_bytes).decode('utf-8')
                
                response = self.groq_client.chat.completions.create(
                    model="llama-3.2-11b-vision-preview", # High performance vision model
                    messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},},],}],
                    max_tokens=800
                )
                analysis_result = response.choices[0].message.content
                speak_func(analysis_result)

            # 4. PRIORITY 2: Local Ollama Fallback (Fully Offline & Private)
            else:
                print("🧠 [VISION ENGINE] Deploying Local Ollama Vision Model...")
                # Ollama library local paths mangti hai images ke liye, isliye temp file save karenge
                temp_path = "temp_screen.jpg"
                screenshot.save(temp_path, format="JPEG", quality=75)
                
                try:
                    # 'llava' or 'bakllava' model local system par installed hona chahiye
                    response = ollama.chat(model='llava', messages=[{'role': 'user', 'content': prompt, 'images': [temp_path]}])
                    analysis_result = response['message']['content']
                    speak_func(analysis_result)
                    
                except Exception as ollama_err:
                    speak_func(f"Local Ollama Vision failed. (Ensure 'llava' model is downloaded via 'ollama run llava'). Error: {ollama_err}")
                finally:
                    # Safe Cleanup
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    
        except Exception as e:
            speak_func(f"Vision system protocol failure: {str(e)}")

    # --- MATHEMATICS SOLVERS ---
    def calculate_arithmetic(self, query):
        """
        1. ARITHMETIC: Basic Operations (+, -, *, /)
        """
        query = query.lower().strip()
        replacements = {
            "plus": "+", "add": "+", 
            "minus": "-", "subtract": "-", 
            "multiplied by": "*", "times": "*", "into": "*", "multiply": "*",
            "divided by": "/", "divide": "/", "over": "/",
            "power of": "**", "power": "**", "raised to": "**",
            "square root of": "sqrt", "root": "sqrt"
        }
        for word, symbol in replacements.items():
            query = query.replace(word, symbol)
        try:
            expr = sympy.sympify(query)
            result = expr.evalf()
            if result.is_Integer:
                return int(result)
            return round(float(result), 6)
        except Exception as e:
            return f"Arithmetic Error: {e}"

    def solve_algebra(self, eq_str, var_str='x'):
        """
        2. ALGEBRA & VARIABLES: Equations solve karna
        """
        try:
            var = sympy.Symbol(var_str)
            if '=' in eq_str:
                lhs, rhs = eq_str.split('=')
                equation = sympy.Eq(sympy.sympify(lhs.strip()), sympy.sympify(rhs.strip()))
            else:
                equation = sympy.sympify(eq_str.strip())
            
            solutions = sympy.solve(equation, var)
            return f"Solutions for {var_str}: {solutions}"
        except Exception as e:
            return f"Algebra Error: {e}"

    def solve_quadratic(self, a, b, c):
        """
        3. QUADRATIC EQUATIONS: ax^2 + bx + c = 0 ke roots aur discriminant nikalna
        """
        try:
            expr = a * self.x**2 + b * self.x + c
            solutions = sympy.solve(expr, self.x)
            discriminant = b**2 - 4*a*c
            return {
                "equation": f"{a}x^2 + {b}x + {c} = 0",
                "roots": solutions,
                "discriminant": discriminant,
                "nature_of_roots": "Real and Distinct" if discriminant > 0 else "Real and Equal" if discriminant == 0 else "Complex Conjugates"
            }
        except Exception as e:
            return f"Quadratic Error: {e}"

    def calculate_calculus(self, expr_str, op_type="derivative", var_str='x', limit_point=0, lower_limit=None, upper_limit=None):
        """
        4. CALCULUS: Derivatives, Integrals, and Limits
        """
        try:
            var = sympy.Symbol(var_str)
            expr = sympy.sympify(expr_str)
            if op_type == "derivative":
                return f"d/d{var_str} ({expr_str}) = {sympy.diff(expr, var)}"
            elif op_type == "integral":
                if lower_limit is not None and upper_limit is not None:
                    val = sympy.integrate(expr, (var, lower_limit, upper_limit))
                    return f"Definite Integral from {lower_limit} to {upper_limit} = {val}"
                return f"Integral ({expr_str}) d{var_str} = {sympy.integrate(expr, var)} + C"
            elif op_type == "limit":
                val = sympy.limit(expr, var, limit_point)
                return f"Limit of ({expr_str}) as {var_str}->{limit_point} = {val}"
            else:
                return "Unsupported calculus operation."
        except Exception as e:
            return f"Calculus Error: {e}"

    def calculate_trigonometry(self, func_name, angle_deg):
        """
        5. TRIGONOMETRY: Sine, Cosine, Tangent (degrees me)
        """
        try:
            angle_rad = sympy.radians(angle_deg)
            func = func_name.lower().strip()
            
            if func in ['sin', 'sine']:
                return f"sin({angle_deg}°) = {float(sympy.sin(angle_rad)):.6f}"
            elif func in ['cos', 'cosine']:
                return f"cos({angle_deg}°) = {float(sympy.cos(angle_rad)):.6f}"
            elif func in ['tan', 'tangent']:
                if angle_deg % 180 == 90:
                    return f"tan({angle_deg}°) = Undefined (Infinity)"
                return f"tan({angle_deg}°) = {float(sympy.tan(angle_rad)):.6f}"
            else:
                return "Unsupported trigonometric function. Use sin, cos, or tan."
        except Exception as e:
            return f"Trigonometry Error: {e}"

    def calculate_statistics(self, data_list):
        """
        6. STATISTICS: Mean, Median, Mode, Variance, and Standard Deviation
        """
        try:
            if not data_list: return "Data list cannot be empty."
            mean_val = np.mean(data_list)
            median_val = np.median(data_list)
            
            counter = Counter(data_list)
            mode_data = counter.most_common(1)
            mode_val = mode_data[0][0] if mode_data else None

            variance_val = np.var(data_list, ddof=1) if len(data_list) > 1 else 0
            std_dev_val = np.std(data_list, ddof=1) if len(data_list) > 1 else 0

            return {
                "data": data_list,
                "mean": round(float(mean_val), 4),
                "median": round(float(median_val), 4),
                "mode": round(float(mode_val), 4) if mode_val is not None else "None",
                "variance": round(float(variance_val), 4),
                "standard_deviation": round(float(std_dev_val), 4)
            }
        except Exception as e:
            return f"Statistics Error: {e}"

    def classify_and_simplify_number(self, num_str):
        """
        7. NUMBER CLASSIFICATION: Rational, Integer, Whole Numbers, and Simplification
        """
        try:
            num = sympy.sympify(num_str)
            is_integer = num.is_integer
            is_rational = num.is_rational
            is_whole = is_integer and num >= 0
            
            result = {
                "input": num_str,
                "is_integer": bool(is_integer),
                "is_rational": bool(is_rational),
                "is_whole_number": bool(is_whole),
            }
            if is_rational:
                result["simplified_fraction"] = str(sympy.nsimplify(num))
            return result
        except Exception as e:
            return f"Number Error: {e}"

    # --- SCIENCE SOLVERS (PHYSICS & CHEMISTRY) ---
    def _solve_chemistry(self, query):
        """Solves chemistry problems like molar mass and balancing equations."""
        try:
            # Stoichiometry check should be first as it's more specific
            if "stoichiometry" in query or ("how much" in query and ("reacts with" in query or "produces" in query)):
                return self._solve_stoichiometry(query)

            # Molar Mass Calculation
            molar_mass_match = re.search(r'(?:molar mass|molecular weight) of ([A-Za-z0-9()]+)', query)
            if molar_mass_match:
                compound_str = molar_mass_match.group(1)
                f = FormulaParser(compound_str)
                return f"The molar mass of {f.formula} is {f.mass:.4f} g/mol."

            balance_match = re.search(r'balance (.*)', query)
            if balance_match:
                equation_str = balance_match.group(1)
                if '=' not in equation_str:
                    return "Please provide a full equation with reactants and products separated by '='."
                
                reactants_str, products_str = [s.strip() for s in equation_str.split('=')]
                reactants = {Substance.from_formula(f.strip()): 1 for f in reactants_str.split('+')}
                products = {Substance.from_formula(f.strip()): 1 for f in products_str.split('+')}
                
                reac, prod = balance_stoichiometry(reactants.keys(), products.keys())
                
                reac_str = ' + '.join([f'{v} {k.formula}' for k, v in reac.items()])
                prod_str = ' + '.join([f'{v} {k.formula}' for k, v in prod.items()])
                
                return f"The balanced equation is: {reac_str} = {prod_str}"
        except Exception as e:
            print(f"Chemistry Solver Error: {e}")
            return "I encountered an error solving the chemistry problem. Please ensure the format is correct."

        return None

    def calculate_statistics(self, query):
        """Handles stoichiometry calculations."""
        try:
            # Regex to extract components for stoichiometry
            # This regex is designed to be somewhat flexible for common phrasing.
            match = re.search(
                r'how much ([A-Za-z0-9()]+) (?:is produced from|from)\s*(\d+\.?\d*)\s*(grams|moles)\s*of\s*([A-Za-z0-9()]+)\s*(?:in the reaction|from the reaction|using the reaction|for the reaction)?\s*(.*)',
                query
            )
            if not match:
                return "For stoichiometry, please provide the target, given quantity, and the equation."

            target_substance_str, given_quantity_str, given_unit, given_substance_str, equation_str = match.groups()
            given_quantity = float(given_quantity_str)
            target_substance_str = target_substance_str.strip()
            given_unit = given_unit.strip()
            given_substance_str = given_substance_str.strip()
            equation_str = equation_str.strip()

            if '=' not in equation_str:
                return "Please provide a full chemical equation with reactants and products separated by '='."

            reactants_str, products_str = [s.strip() for s in equation_str.split('=')]
            
            # Parse substances for balancing
            unbalanced_reactants = [Substance.from_formula(f.strip()) for f in reactants_str.split('+')]
            unbalanced_products = [Substance.from_formula(f.strip()) for f in products_str.split('+')]

            # Balance the equation
            reac_coeffs, prod_coeffs = balance_stoichiometry(unbalanced_reactants, unbalanced_products)
            balanced_map = {sub.formula: coeff for sub, coeff in reac_coeffs.items()}
            balanced_map.update({sub.formula: coeff for sub, coeff in prod_coeffs.items()})

            # Reconstruct balanced equation to easily get coefficients by formula string
            balanced_reactants_map = {sub.formula: reac_coeffs[sub] for sub in reac_coeffs}
            balanced_products_map = {sub.formula: prod_coeffs[sub] for sub in prod_coeffs}
            molar_masses = {f: FormulaParser(f).mass for f in balanced_map.keys()}

            # Find molar masses for all involved substances
            molar_masses = {}
            all_substances_formulas = list(balanced_reactants_map.keys()) + list(balanced_products_map.keys())
            for sub_formula in all_substances_formulas:
                try:
                    molar_masses[sub_formula] = FormulaParser(sub_formula).mass
                except Exception as e:
                    print(f"Molar mass calculation error for {sub_formula}: {e}")
                    return f"Could not determine molar mass for '{sub_formula}'. Please check the chemical formula."

            # Get coefficients for given and target substances
            given_coeff = balanced_reactants_map.get(given_substance_str) or balanced_products_map.get(given_substance_str)
            target_coeff = balanced_reactants_map.get(target_substance_str) or balanced_products_map.get(target_substance_str)
            if not given_coeff or not target_coeff:
                return "One of the substances was not found in the balanced equation."

            if given_coeff is None:
                return f"'{given_substance_str}' was not found in the balanced equation. Please check the equation and substance name."
            if target_coeff is None:
                return f"'{target_substance_str}' was not found in the balanced equation. Please check the equation and substance name."

            # Perform calculation
            if given_unit == "grams":
                moles_given = given_quantity / molar_masses[given_substance_str]
            elif given_unit == "moles":
                moles_given = given_quantity
            else:
                return f"Unsupported unit '{given_unit}'. Currently only 'grams' and 'moles' are supported for stoichiometry input."

            moles_target = (moles_given / given_coeff) * target_coeff
            mass_target = moles_target * molar_masses[target_substance_str] # Output in grams by default

            return (
                f"For the reaction: {equation_str}, "
                f"from {given_quantity} {given_unit} of {given_substance_str}, "
                f"approximately {mass_target:.4f} grams of {target_substance_str} can be produced."
            )
        except Exception as e:
            print(f"Stoichiometry Solver Error: {e}")
            return "I encountered an error solving the stoichiometry problem. Please ensure the query format and chemical formulas are correct."

    def classify_and_simplify_number(self, query):
        """Handles common unit conversions."""
        try:
            match = re.search(r'convert (\d+\.?\d*)\s*([a-zA-Z]+)\s*(?:to|into)\s*([a-zA-Z]+)', query)
            if not match:
                return "Please specify the quantity and units to convert."

            value, from_unit, to_unit = float(match.group(1)), match.group(2).lower(), match.group(3).lower()

            # Length
            conversions = {
                ("meters", "feet"): 3.28084, ("feet", "meters"): 1/3.28084,
                ("km", "miles"): 0.621371, ("miles", "km"): 1/0.621371,
                ("inches", "cm"): 2.54, ("cm", "inches"): 1/2.54,
            }
            # Mass
            conversions.update({
                ("kg", "pounds"): 2.20462, ("pounds", "kg"): 1/2.20462,
            })

            # Normalize units (e.g., meter -> meters)
            from_unit_norm = from_unit + 's' if not from_unit.endswith('s') else from_unit
            to_unit_norm = to_unit + 's' if not to_unit.endswith('s') else to_unit

            # Temperature (special case)
            if from_unit in ["celsius", "c"] and to_unit in ["fahrenheit", "f"]:
                result = (value * 9/5) + 32
                return f"{value}°C is {result:.2f}°F."
            elif from_unit in ["fahrenheit", "f"] and to_unit in ["celsius", "c"]:
                result = (value - 32) * 5/9
                return f"{value}°F is {result:.2f}°C."
            elif from_unit in ["celsius", "c"] and to_unit in ["kelvin", "k"]:
                result = value + 273.15
                return f"{value}°C is {result:.2f}K."
            elif from_unit in ["kelvin", "k"] and to_unit in ["celsius", "c"]:
                result = value - 273.15
                return f"{value}K is {result:.2f}°C."

            # General conversions
            if (from_unit_norm, to_unit_norm) in conversions:
                result = value * conversions[(from_unit_norm, to_unit_norm)]
                return f"{value} {from_unit} is {result:.4f} {to_unit}."

            return f"Commander, I cannot perform the conversion from {from_unit} to {to_unit} at this moment."

        except Exception as e:
            print(f"Unit Conversion Error: {e}")
            return "I encountered an error during unit conversion."

    def handle_query(self, query):
        """Main router to decide which function to call based on the query."""
        query = query.lower()

        # Priority 1: Scientific Calculations (Physics, Chemistry)
        if any(k in query for k in ["balance", "molar mass", "molecular weight", "stoichiometry"]):
            return self._solve_chemistry(query)
        if any(k in query for k in self.physics_formulas.keys()) and "calculate" in query:
            return self._solve_physics(query)
        if "convert" in query and ("to" in query or "into" in query):
            return self._convert_units(query)

        # Priority 2: Advanced Mathematics
        # Statistics
        if "statistics of" in query:
            data_str = query.split("statistics of")[-1]
            try:
                data_list = [float(i) for i in re.findall(r'-?\d+\.?\d*', data_str)]
                if data_list:
                    return str(self.calculate_statistics(data_list))
            except:
                return "Could not parse the data for statistics."

        # Trigonometry
        trig_match = re.search(r'(sin|cos|tan|sine|cosine|tangent) of (\d+\.?\d*)', query)
        if trig_match:
            func_name = trig_match.group(1)
            angle = float(trig_match.group(2))
            return self.calculate_trigonometry(func_name, angle)

        # Calculus
        calc_match = re.search(r'(derivative|integral|limit) of (.*)', query)
        if calc_match:
            op_type = calc_match.group(1)
            expr_str = calc_match.group(2).split(" with respect to ")[0]
            return self.calculate_calculus(expr_str, op_type=op_type)

        # Quadratic
        quad_match = re.search(r'solve quadratic with a as (-?\d+\.?\d*), b as (-?\d+\.?\d*), and c as (-?\d+\.?\d*)', query)
        if quad_match:
            a, b, c = map(float, quad_match.groups())
            return str(self.solve_quadratic(a, b, c))

        # Algebra
        if "solve" in query and "=" in query:
            eq_str = query.split("solve")[-1].strip()
            return self.solve_algebra(eq_str)

        # Number Classification
        num_match = re.search(r'classify the number (-?\d+\.?\d*)', query)
        if num_match:
            num_str = num_match.group(1)
            return str(self.classify_and_simplify_number(num_str))

        # Priority 3: Basic Arithmetic (Fallback)
        if any(word in query for word in ["calculate", "what is"]) and re.search(r'\d', query):
            # Clean up trigger words to get the pure expression
            expr_str = query.replace("calculate", "").replace("what is", "").strip()
            # A final check to ensure it's not a different command that happens to have numbers
            if not any(k in expr_str for k in ["statistics", "trigonometry", "calculus", "solve"]):
                 return str(self.calculate_arithmetic(expr_str))

        return None
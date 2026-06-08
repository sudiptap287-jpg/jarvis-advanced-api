import os
import socket
from cryptography.fernet import Fernet

KEY_FILE = "master_access.key"

def get_cipher():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f: f.write(key)
    else:
        key = open(KEY_FILE, "rb").read()
    return Fernet(key)

cipher = get_cipher()

def encrypt_now(text: str):
    return cipher.encrypt(text.encode())

def check_online():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except:
        return False
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
import time
from typing import Self
import requests
import threading

# Update this to match the DB path in your main.py
DB_PATH = "jarvis_memory.db" 

class JarvisHistoryGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Jarvis API - Premium Cache Manager")
        self.root.geometry("700x550")
        self.root.configure(bg="#f0f2f5")

        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self):
        # Header
        header = tk.Label(self.root, text="PROMPT HISTORY MANAGER", font=("Arial", 16, "bold"), bg="#f0f2f5")
        header.pack(pady=10)

        # Search Frame
        search_frame = tk.Frame(self.root, bg="#f0f2f5")
        search_frame.pack(fill="x", padx=20)
        
        tk.Label(search_frame, text="Search Keywords:", bg="#f0f2f5").pack(side="left")
        self.search_entry = tk.Entry(search_frame)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh_data())

        # List of Prompts (Treeview)
        self.tree = ttk.Treeview(self.root, columns=("Prompt", "Date"), show='headings')
        self.tree.heading("Prompt", text="User Prompt")
        self.tree.heading("Date", text="Saved At")
        self.tree.column("Prompt", width=450)
        self.tree.column("Date", width=150)
        self.tree.pack(fill="both", expand=True, padx=20, pady=10)
        self.tree.bind("<<TreeviewSelect>>", self.load_selected)

        # Edit Section
        edit_frame = tk.LabelFrame(self.root, text=" Edit Selected Entry ", bg="#f0f2f5", padx=10, pady=10)
        edit_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(edit_frame, text="Response:", bg="#f0f2f5").pack(anchor="w")
        self.edit_box = tk.Text(edit_frame, height=5)
        self.edit_box.pack(fill="x", pady=5)

        # Action Buttons
        btn_frame = tk.Frame(self.root, bg="#f0f2f5")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Update Response", command=self.update_entry, bg="#4caf50", fg="white", width=15).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Delete Entry", command=self.delete_entry, bg="#f44336", fg="white", width=15).pack(side="left", padx=5)

    def refresh_data(self):
        """Fetches data from jarvis_memory.db and updates the list."""
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        keyword = f"%{self.search_entry.get()}%"
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            # Searching both prompt and response
            cursor.execute("SELECT prompt, timestamp FROM prompt_cache WHERE prompt LIKE ? OR response LIKE ?", (keyword, keyword))
            for row in cursor.fetchall():
                # Formatting the date
                date_val = row[1] if isinstance(row[1], str) else time.strftime('%Y-%m-%d', time.localtime(row[1]))
                self.tree.insert("", "end", values=(row[0], date_val))
            conn.close()
        except Exception as e:
            print(f"DB Error: {e}")

    def load_selected(self, event):
        """Loads the full response into the edit box when you click a list item."""
        selected = self.tree.selection()
        if not selected: return
        prompt_val = self.tree.item(selected[0])['values'][0]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT response FROM prompt_cache WHERE prompt = ?", (prompt_val,))
        res = cursor.fetchone()
        conn.close()

        if res:
            self.edit_box.delete("1.0", "end")
            self.edit_box.insert("1.0", res[0])

    def update_entry(self):
        """Saves the edited text back to the database."""
        selected = self.tree.selection()
        if not selected: return
        prompt_val = self.tree.item(selected[0])['values'][0]
        new_text = self.edit_box.get("1.0", "end").strip()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE prompt_cache SET response = ? WHERE prompt = ?", (new_text, prompt_val))
        conn.commit()
        conn.close()
        messagebox.showinfo("Success", "Response updated successfully!")

    def delete_entry(self):
        """Deletes the record from the database."""
        selected = self.tree.selection()
        if not selected: return
        prompt_val = self.tree.item(selected[0])['values'][0]

        if messagebox.askyesno("Confirm", "Delete this history entry?"):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM prompt_cache WHERE prompt = ?", (prompt_val,))
            conn.commit()
            conn.close()
            self.refresh_data()
            self.edit_box.delete("1.0", "end")

if __name__ == "__main__":
    root = tk.Tk()
    app = JarvisHistoryGUI(root)
    root.mainloop()

    # Yeh line Header ke niche add karein
Self.status_label = tk.Label(Self.root, text="API Status: Checking...", fg="orange", bg="#f0f2f5", font=("Arial", 10, "bold"))
Self.status_label.pack(pady=5)

# Status update loop start karne ke liye
Self.check_api_status()

def check_api_status(self):
    def worker():
        try:
            # Aapke FastAPI ka local URL
            response = requests.get("http://127.0.0.1:8000/", timeout=2)
            if response.status_code == 200:
                self.status_label.config(text="● API ONLINE", fg="green")
            else:
                self.status_label.config(text="● API ERROR", fg="orange")
        except:
            self.status_label.config(text="● API OFFLINE (Server Down)", fg="red")
        
        # Har 5 second baad dobara check karega
        self.root.after(5000, self.check_api_status)

    # Threading use kar rahe hain taaki GUI freeze na ho
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
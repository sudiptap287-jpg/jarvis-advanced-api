import sqlite3
def setup_database():
    # Connects to your existing jarvis_memory.db
    conn = sqlite3.connect('jarvis_memory.db')
    cursor = conn.cursor()

    # Creates the table for Function Calling logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS call_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            func_name TEXT NOT NULL,
            result TEXT,
            time DATETIME
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database 'jarvis_memory.db' is now ready for Function Calling!")

if __name__ == "__main__":
    setup_database()

def init_db():
    # We will use your existing jarvis_ai.db file
    conn = sqlite3.connect("jarvis_ai.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS secure_data (
            record_id TEXT PRIMARY KEY,
            blob_data BLOB,
            timestamp DATETIME,
            synced INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    print("Database 'jarvis_ai.db' initialized successfully!")

if __name__ == "__main__":
    init_db()
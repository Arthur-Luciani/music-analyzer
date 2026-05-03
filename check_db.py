import sqlite3
import os

db_path = "storage/sessions.db"
if not os.path.exists(db_path):
    print(f"File not found: {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sessions")
    count = cursor.fetchone()[0]
    print(f"Total sessions in DB: {count}")
    conn.close()

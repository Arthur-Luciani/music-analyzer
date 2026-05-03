import sqlite3
from pathlib import Path

db_path = Path("storage/sessions.db")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(f"Tables: {cursor.fetchall()}")
conn.close()

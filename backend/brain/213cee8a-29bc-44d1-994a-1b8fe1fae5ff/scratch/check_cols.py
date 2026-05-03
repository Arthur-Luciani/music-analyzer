import sqlite3
from pathlib import Path

db_path = Path("storage/sessions.db")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(sessions)")
print(f"Columns: {cursor.fetchall()}")
conn.close()

import sqlite3
import json
from pathlib import Path

db_path = Path("storage/sessions.db")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()
cursor.execute("SELECT stems_json FROM sessions WHERE id = '918ea4a6-625e-4d75-83ab-50bfd7c89c20'")
row = cursor.fetchone()
if row:
    print(f"Stems JSON: {row[0]}")
else:
    print("Session not found in DB")
conn.close()

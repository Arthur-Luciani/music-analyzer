
import sqlite3
import os

db_path = r"c:\git\music-analyzer\storage\sessions.db"
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, track_title, artist FROM sessions WHERE session_code = 'MX-022'")
row = cursor.fetchone()
if row:
    print(f"ID: {row[0]}")
    print(f"Title: {row[1]}")
    print(f"Artist: {row[2]}")
else:
    print("Session MX-022 not found")
conn.close()

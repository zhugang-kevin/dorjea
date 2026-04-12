import sqlite3, os
os.makedirs("memory", exist_ok=True)
conn = sqlite3.connect("memory/aifactory.db")
with open("memory/schema.sql", "r") as f:
    conn.executescript(f.read())
conn.commit()
conn.close()
print("Database initialized successfully")

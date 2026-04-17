import sqlite3, os
db_path = "memory/aifactory.db"
if not os.path.exists(db_path):
    print("FAILED: Database file not found")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = ",".join([r[0] for r in cursor.fetchall()])
        conn.close()
        print("OK: " + tables)
    except Exception as e:
        print("FAILED: " + str(e))

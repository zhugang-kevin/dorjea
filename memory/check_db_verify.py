import sqlite3
try:
    conn = sqlite3.connect('memory/aifactory.db')
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    conn.close()
    print('OK:' + ','.join([t[0] for t in tables]))
except Exception as e:
    print('FAIL:' + str(e))
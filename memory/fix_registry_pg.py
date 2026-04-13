with open("agents/meta_agent/registry.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./memory/aifactory.db")
if DB_PATH.startswith("sqlite:///"):
    DB_PATH = DB_PATH.replace("sqlite:///", "")


def _get_connection() -> sqlite3.Connection:
    \"\"\"
    Return a SQLite connection with row factory set.
    Creates the database file if it does not exist.
    \"\"\"
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn"""

new = """DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./memory/aifactory.db")
USE_POSTGRES = DATABASE_URL.startswith("postgresql://")

if not USE_POSTGRES:
    DB_PATH = DATABASE_URL.replace("sqlite:///", "")
else:
    DB_PATH = None


def _get_connection():
    \"\"\"
    Return a database connection — SQLite for dev, PostgreSQL for prod.
    \"\"\"
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _fetchall(cursor):
    \"\"\"Return rows as list of dicts for both SQLite and PostgreSQL.\"\"\"
    if USE_POSTGRES:
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    return [dict(row) for row in cursor.fetchall()]


def _fetchone(cursor):
    \"\"\"Return one row as dict for both SQLite and PostgreSQL.\"\"\"
    row = cursor.fetchone()
    if row is None:
        return None
    if USE_POSTGRES:
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))
    return dict(row)"""

content = content.replace(old, new)

# Fix fetchone and fetchall calls
content = content.replace(
    "result = cursor.fetchone()\n        conn.close()\n        return result is not None",
    "result = cursor.fetchone()\n        conn.close()\n        return result is not None"
)
content = content.replace(
    "rows = cursor.fetchall()\n        conn.close()\n        return [dict(row) for row in rows]",
    "rows = _fetchall(cursor)\n        conn.close()\n        return rows"
)
content = content.replace(
    "row  = conn.execute(\"SELECT id FROM agents WHERE name = ? AND status != 'archived'\",",
    "cursor = conn.cursor()\n        cursor.execute(\"SELECT id FROM agents WHERE name = %s AND status != 'archived'\" if USE_POSTGRES else \"SELECT id FROM agents WHERE name = ? AND status != 'archived'\","
)

with open("agents/meta_agent/registry.py", "w", encoding="utf-8") as f:
    f.write(content)
print("registry.py updated for PostgreSQL support")

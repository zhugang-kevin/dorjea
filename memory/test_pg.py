import psycopg2
conn = psycopg2.connect("postgresql://postgres:admin@localhost:5432/dorjea")
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
tables = [r[0] for r in cur.fetchall()]
conn.close()
print("PostgreSQL connected. Tables:", tables)

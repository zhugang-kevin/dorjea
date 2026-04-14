with open("agents/meta_agent/registry.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """        rows = _fetchall(cursor)
        conn.close()
        return rows
    except Exception:
        return []"""

new = """        rows = _fetchall(cursor)
        conn.close()
        return [_enrich_agent(row) for row in rows]
    except Exception:
        return []"""

content = content.replace(old, new)

with open("agents/meta_agent/registry.py", "w", encoding="utf-8") as f:
    f.write(content)
print("list_agents fixed with enrich")

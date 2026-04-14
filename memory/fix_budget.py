with open("self_token/budget_manager.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """def get_daily_usage():
    if not METRICS_PATH.exists():
        return 0
    today = datetime.utcnow().date().isoformat()
    total = 0
    try:
        with open(METRICS_PATH, encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line.strip())
                if entry.get("timestamp", "").startswith(today):
                    total += entry.get("total_tokens", 0)
    except Exception:
        pass
    return total"""

new = """def get_daily_usage(hours=48):
    if not METRICS_PATH.exists():
        return 0
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    total = 0
    try:
        with open(METRICS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("timestamp", "") >= cutoff:
                    total += entry.get("total_tokens", 0)
    except Exception:
        pass
    return total"""

content = content.replace(old, new)
with open("self_token/budget_manager.py", "w", encoding="utf-8") as f:
    f.write(content)
print("budget_manager.py fixed — now shows 48h usage")

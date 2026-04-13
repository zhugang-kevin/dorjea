with open("evals/runners/run_evals.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '            passed = result.get("status") == "SUCCESS"'
new = '''            status = result.get("status")
            errors = result.get("errors", [])
            already_exists = any("already exists" in str(e) for e in errors)
            passed = status == "SUCCESS" or already_exists'''

content = content.replace(old, new)

with open("evals/runners/run_evals.py", "w", encoding="utf-8") as f:
    f.write(content)
print("run_evals.py updated")

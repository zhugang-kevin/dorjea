with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

old = 'allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"]'
new = 'allow_origins=["*"]'

content = content.replace(old, new)

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("CORS fixed")

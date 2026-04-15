with open("Dockerfile", "r", encoding="utf-8") as f:
    content = f.read()

old = "CMD uvicorn agents.meta_agent.api:app --host 0.0.0.0 --port ${PORT:-8000}"
new = 'CMD ["python", "start.py"]'

content = content.replace(old, new)

with open("Dockerfile", "w", encoding="utf-8") as f:
    f.write(content)
print("Dockerfile fixed with Python startup script")

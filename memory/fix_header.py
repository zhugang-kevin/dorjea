with open("agents/meta_agent/api.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "from fastapi import FastAPI, HTTPException, Request",
    "from fastapi import FastAPI, HTTPException, Request, Header"
)

content = content.replace(
    "from fastapi import Header\nfrom typing import Optional",
    "from typing import Optional"
)

with open("agents/meta_agent/api.py", "w", encoding="utf-8") as f:
    f.write(content)
print("fixed")

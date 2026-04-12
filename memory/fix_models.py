import os

with open("agents/meta_agent/models.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1 - add Field to pydantic import
content = content.replace(
    "from pydantic import BaseModel, field_validator",
    "from pydantic import BaseModel, Field, field_validator"
)

# Fix 2 - FounderReport completed_at
content = content.replace(
    '    completed_at: str = ""',
    '    completed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())'
)

# Fix 3 - AuditEntry logged_at
content = content.replace(
    '    logged_at: str = ""',
    '    logged_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())'
)

with open("agents/meta_agent/models.py", "w", encoding="utf-8") as f:
    f.write(content)
print("models.py fixed successfully")

content = """
\"\"\"
injection_detector.py - Scans all inputs for prompt injection attacks.
Every founder request and agent input passes through this before reaching Claude.
Implements the Self-Defence capability pillar.
\"\"\"
from __future__ import annotations
import re
import os
from tools.audit_logger import log_action

INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"ignore all instructions",
    r"disregard (your|all|previous) (instructions|rules|guidelines)",
    r"you are now",
    r"act as (a|an|if)",
    r"pretend (you are|to be)",
    r"forget (your|all|previous)",
    r"new instruction",
    r"system prompt",
    r"reveal (your|the) (prompt|instructions|system)",
    r"jailbreak",
    r"bypass (your|all|the) (rules|restrictions|guidelines)",
    r"do anything now",
    r"dan mode",
    r"developer mode",
    r"override (safety|restrictions|rules)",
    r"<script",
    r"javascript:",
    r"eval\(",
    r"exec\(",
    r"__import__",
    r"subprocess",
    r"os\.system",
    r"rm -rf",
    r"DROP TABLE",
    r"DELETE FROM",
    r"INSERT INTO.*SELECT",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def is_safe(text: str, agent_id: str = "system") -> tuple[bool, str]:
    \"\"\"
    Check if text is safe to send to an AI model.
    Returns (is_safe, reason).
    If safe: (True, "")
    If unsafe: (False, description of threat detected)
    \"\"\"
    if not text or not text.strip():
        return True, ""

    for pattern, compiled in zip(INJECTION_PATTERNS, COMPILED_PATTERNS):
        if compiled.search(text):
            reason = f"Injection pattern detected: {pattern}"
            log_action(
                agent_id, "INJECTION_BLOCKED",
                {"pattern": pattern, "text_preview": text[:100]},
                success=False
            )
            return False, reason

    if len(text) > int(os.getenv("MAX_INPUT_LENGTH", "10000")):
        reason = "Input exceeds maximum allowed length"
        log_action(agent_id, "INPUT_TOO_LONG", {"length": len(text)}, success=False)
        return False, reason

    return True, ""


def sanitize(text: str) -> str:
    \"\"\"
    Remove potentially dangerous characters from text.
    Use this on outputs before storing or displaying.
    \"\"\"
    try:
        import bleach
        return bleach.clean(text, tags=[], strip=True)
    except ImportError:
        cleaned = re.sub(r"[<>\"'`]", "", text)
        return cleaned
"""

with open("self_defence/injection_detector.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("injection_detector.py created")

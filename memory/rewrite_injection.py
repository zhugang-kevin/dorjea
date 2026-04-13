content = """
import re
import os
from tools.audit_logger import log_action

INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"ignore all instructions",
    r"disregard your instructions",
    r"you are now",
    r"act as if",
    r"pretend you are",
    r"forget your instructions",
    r"new instruction",
    r"system prompt",
    r"reveal your prompt",
    r"jailbreak",
    r"bypass your rules",
    r"do anything now",
    r"dan mode",
    r"developer mode",
    r"override safety",
    r"__import__",
    r"subprocess",
    r"os.system",
    r"DROP TABLE",
    r"DELETE FROM",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def is_safe(text, agent_id="system"):
    if not text or not text.strip():
        return True, ""
    for pattern, compiled in zip(INJECTION_PATTERNS, COMPILED):
        if compiled.search(text):
            reason = "Injection pattern detected: " + pattern
            log_action(agent_id, "INJECTION_BLOCKED",
                       {"pattern": pattern, "text_preview": text[:100]},
                       success=False)
            return False, reason
    max_len = int(os.getenv("MAX_INPUT_LENGTH", "10000"))
    if len(text) > max_len:
        reason = "Input exceeds maximum allowed length"
        log_action(agent_id, "INPUT_TOO_LONG", {"length": len(text)}, success=False)
        return False, reason
    return True, ""


def sanitize(text):
    cleaned = re.sub(r"[<>]", "", text)
    return cleaned
"""

with open("self_defence/injection_detector.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("injection_detector.py rewritten successfully")

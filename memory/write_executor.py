content = """
import subprocess
import tempfile
import os
import sys
from pathlib import Path
from datetime import datetime
from agents.meta_agent.audit_logger import write_audit_entry
from agents.meta_agent.models import AuditEntry

SANDBOX_DIR = Path("logs/sandbox")
MAX_RUNTIME_SECONDS = 30
ALLOWED_LANGUAGES = ["python", "javascript", "bash"]


def execute_code(agent_name, task_id, code, language="python"):
    if language not in ALLOWED_LANGUAGES:
        return {"success": False, "output": "", "error": "Language not allowed: " + language, "runtime_ms": 0}

    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

    write_audit_entry(AuditEntry(
        agent_id=agent_name, task_id=task_id,
        action="CODE_EXECUTION_STARTED",
        details={"language": language, "code_preview": code[:100]},
        success=True,
    ))

    ext = {"python": ".py", "javascript": ".js", "bash": ".sh"}[language]
    cmd = {"python": [sys.executable], "javascript": ["node"], "bash": ["bash"]}[language]

    start = datetime.utcnow()
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=ext, dir=str(SANDBOX_DIR),
                                         delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        result = subprocess.run(
            cmd + [tmp_path],
            capture_output=True, text=True,
            timeout=MAX_RUNTIME_SECONDS,
            cwd=str(SANDBOX_DIR),
        )
        runtime_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

        os.unlink(tmp_path)

        success = result.returncode == 0
        write_audit_entry(AuditEntry(
            agent_id=agent_name, task_id=task_id,
            action="CODE_EXECUTION_COMPLETED",
            details={"success": success, "runtime_ms": runtime_ms,
                     "returncode": result.returncode},
            success=success,
        ))

        return {
            "success": success,
            "output": result.stdout[:3000],
            "error": result.stderr[:1000] if result.stderr else "",
            "returncode": result.returncode,
            "runtime_ms": runtime_ms,
            "language": language,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": "Execution timed out after " + str(MAX_RUNTIME_SECONDS) + "s", "runtime_ms": MAX_RUNTIME_SECONDS * 1000}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e), "runtime_ms": 0}


def run_tests(agent_name, task_id, test_code):
    return execute_code(agent_name, task_id, test_code, language="python")


def validate_code_output(output, expected_keywords):
    if not expected_keywords:
        return True, []
    missing = [kw for kw in expected_keywords if kw.lower() not in output.lower()]
    return len(missing) == 0, missing
"""

with open("agents/runtime/code_executor.py", "w", encoding="utf-8") as f:
    f.write(content.strip())
print("code_executor.py created")

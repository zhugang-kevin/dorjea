import os
import subprocess
import sys

port = os.environ.get("PORT") or os.environ.get("API_PORT", "8000")
cmd = [sys.executable, "-m", "uvicorn", "agents.meta_agent.api:app", "--host", "0.0.0.0", "--port", port]
subprocess.run(cmd)

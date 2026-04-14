import sys
sys.path.insert(0, ".")
from agents.runtime.code_executor import execute_code
result = execute_code("test_agent", "task_001", "print('Hello from sandbox')\nprint('Code executor works')")
print("Success:", result["success"])
print("Output:", result["output"].strip())
print("Runtime:", result["runtime_ms"], "ms")

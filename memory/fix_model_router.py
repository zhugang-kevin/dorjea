with open("agents/runtime/model_router.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''def call_with_fallback(prompt, task_id="default", system=None):
    result = _try_claude(prompt, task_id, system)
    if result["error"]:
        result = _try_openai(prompt, task_id, system)
    if result["error"]:
        result = _try_deepseek(prompt, task_id, system)
    return result'''

new = '''def call_with_fallback(prompt, task_id="default", system=None):
    import os
    primary = os.getenv("PRIMARY_MODEL", "claude-sonnet-4-6")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    use_openai_first = (
        not anthropic_key or
        not anthropic_key.startswith("sk-ant") or
        "gpt" in primary.lower()
    )
    if use_openai_first:
        result = _try_openai(prompt, task_id, system)
        if result["error"]:
            result = _try_claude(prompt, task_id, system)
        if result["error"]:
            result = _try_deepseek(prompt, task_id, system)
    else:
        result = _try_claude(prompt, task_id, system)
        if result["error"]:
            result = _try_openai(prompt, task_id, system)
        if result["error"]:
            result = _try_deepseek(prompt, task_id, system)
    return result'''

content = content.replace(old, new)
with open("agents/runtime/model_router.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Model router updated — OpenAI first when no valid Anthropic key")

with open("agents/runtime/ai_clients.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "    def _get_client(self) -> OpenAI:\n        \"\"\"Create client fresh each call to always use current env vars.\"\"\"\n        api_key = os.getenv(\"OPENAI_API_KEY\", \"\")\n        if not api_key:\n            raise ValueError(\"OPENAI_API_KEY not set in environment.\")\n        return OpenAI(api_key=api_key)"

new = "    def _get_client(self) -> OpenAI:\n        \"\"\"Create client fresh each call to always use current env vars.\"\"\"\n        import httpx\n        api_key = os.getenv(\"OPENAI_API_KEY\", \"\")\n        if not api_key:\n            raise ValueError(\"OPENAI_API_KEY not set in environment.\")\n        base_url = os.getenv(\"OPENAI_BASE_URL\", \"https://api.openai.com/v1\")\n        return OpenAI(api_key=api_key, base_url=base_url, http_client=httpx.Client(proxy='socks5://127.0.0.1:1080'))"

content = content.replace(old, new)

with open("agents/runtime/ai_clients.py", "w", encoding="utf-8") as f:
    f.write(content)
print("OpenAIClient updated with custom base URL support")

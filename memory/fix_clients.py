with open("agents/runtime/ai_clients.py", "r", encoding="utf-8") as f:
    content = f.read()

# Remove load_dotenv from ai_clients - let the caller handle it
# Add lazy loading to ClaudeClient and OpenAIClient

new_content = """\"\"\"
ai_clients.py - Claude and OpenAI API wrappers.
All AI calls in the project go through these classes.
Never call the APIs directly anywhere else.
\"\"\"
from __future__ import annotations
import os
from typing import Optional
import anthropic
from openai import OpenAI


class ClaudeClient:
    \"\"\"
    Wrapper for Anthropic Claude API calls.
    Reads model name and API key from environment on every call.
    Never hardcodes model names or secrets.
    \"\"\"

    def __init__(self) -> None:
        \"\"\"Initialise Claude client from environment variables.\"\"\"
        self.model = os.getenv("PRIMARY_MODEL", "claude-sonnet-4-6")
        self.max_tokens = 4096

    def _get_client(self) -> anthropic.Anthropic:
        \"\"\"Create client fresh each call to always use current env vars.\"\"\"
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment.")
        return anthropic.Anthropic(api_key=api_key)

    def call(
        self,
        prompt: str,
        system: str = "",
        max_tokens: Optional[int] = None,
    ) -> dict:
        \"\"\"
        Call Claude with a prompt and optional system message.
        Returns dict with keys: text, input_tokens, output_tokens, error.
        \"\"\"
        try:
            client = self._get_client()
            messages = [{"role": "user", "content": prompt}]
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                system=system or "You are a helpful AI assistant.",
                messages=messages,
            )
            return {
                "text": response.content[0].text,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                "error": None,
            }
        except ValueError as e:
            return {"text": "", "input_tokens": 0, "output_tokens": 0,
                    "total_tokens": 0, "error": str(e)}
        except anthropic.AuthenticationError:
            return {"text": "", "input_tokens": 0, "output_tokens": 0,
                    "total_tokens": 0, "error": "Claude API key is invalid or missing."}
        except anthropic.RateLimitError:
            return {"text": "", "input_tokens": 0, "output_tokens": 0,
                    "total_tokens": 0, "error": "Claude rate limit exceeded. Wait and retry."}
        except Exception as e:
            return {"text": "", "input_tokens": 0, "output_tokens": 0,
                    "total_tokens": 0, "error": f"Claude API error: {str(e)}"}


class OpenAIClient:
    \"\"\"
    Wrapper for OpenAI GPT API calls.
    Used exclusively as the independent verifier.
    Never hardcodes model names or secrets.
    \"\"\"

    def __init__(self) -> None:
        \"\"\"Initialise OpenAI client from environment variables.\"\"\"
        self.model = os.getenv("VERIFIER_MODEL", "gpt-4o")
        self.max_tokens = 2048

    def _get_client(self) -> OpenAI:
        \"\"\"Create client fresh each call to always use current env vars.\"\"\"
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment.")
        return OpenAI(api_key=api_key)

    def call(
        self,
        prompt: str,
        system: str = "",
        max_tokens: Optional[int] = None,
    ) -> dict:
        \"\"\"
        Call OpenAI GPT with a prompt and optional system message.
        Returns dict with keys: text, input_tokens, output_tokens, error.
        \"\"\"
        try:
            client = self._get_client()
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                messages=messages,
            )
            usage = response.usage
            return {
                "text": response.choices[0].message.content,
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "error": None,
            }
        except ValueError as e:
            return {"text": "", "input_tokens": 0, "output_tokens": 0,
                    "total_tokens": 0, "error": str(e)}
        except Exception as e:
            return {"text": "", "input_tokens": 0, "output_tokens": 0,
                    "total_tokens": 0, "error": f"OpenAI API error: {str(e)}"}
"""

with open("agents/runtime/ai_clients.py", "w", encoding="utf-8") as f:
    f.write(new_content.strip())
print("ai_clients.py fixed successfully")

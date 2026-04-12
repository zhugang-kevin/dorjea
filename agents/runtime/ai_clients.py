"""
ai_clients.py — Claude and OpenAI API wrappers.
All AI calls in the project go through these classes.
Never call the APIs directly anywhere else.
"""
from __future__ import annotations
import os
from typing import Optional
import anthropic
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class ClaudeClient:
    """
    Wrapper for Anthropic Claude API calls.
    Reads model name and API key from environment.
    Never hardcodes model names or secrets.
    """

    def __init__(self) -> None:
        """Initialise Claude client from environment variables."""
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = os.getenv("PRIMARY_MODEL", "claude-sonnet-4-6")
        self.max_tokens = 4096
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def call(
        self,
        prompt: str,
        system: str = "",
        max_tokens: Optional[int] = None,
    ) -> dict:
        """
        Call Claude with a prompt and optional system message.
        Returns dict with keys: text, input_tokens, output_tokens, error.
        """
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.client.messages.create(
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
    """
    Wrapper for OpenAI GPT API calls.
    Used exclusively as the independent verifier.
    Never hardcodes model names or secrets.
    """

    def __init__(self) -> None:
        """Initialise OpenAI client from environment variables."""
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("VERIFIER_MODEL", "gpt-4o")
        self.max_tokens = 2048
        self.client = OpenAI(api_key=self.api_key)

    def call(
        self,
        prompt: str,
        system: str = "",
        max_tokens: Optional[int] = None,
    ) -> dict:
        """
        Call OpenAI GPT with a prompt and optional system message.
        Returns dict with keys: text, input_tokens, output_tokens, error.
        """
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = self.client.chat.completions.create(
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
        except Exception as e:
            return {"text": "", "input_tokens": 0, "output_tokens": 0,
                    "total_tokens": 0, "error": f"OpenAI API error: {str(e)}"}

"""
Lightweight, swappable LLM client for OCTO coprocessors.

Supports OpenAI, Anthropic, Moonshot/Kimi, vLLM, and local/Ollama endpoints
via environment configuration. Falls back to a deterministic placeholder when
no backend is available so pipelines can still be tested offline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict[str, int] | None = None


class LLMClient:
    """Thin wrapper over common LLM providers.

    Usage:
        client = LLMClient.from_env()
        resp = client.complete("What is the capital of France?")
    """

    def __init__(
        self,
        model: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ):
        self.model = model or os.getenv("OCTO_LLM_MODEL", "gpt-4o")
        self.provider = (provider or os.getenv("OCTO_LLM_PROVIDER", "openai")).lower()
        self.base_url = base_url or self._default_base_url(self.provider)
        self.api_key = api_key or self._default_api_key(self.provider)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._clients: dict[str, Any] = {}

    @staticmethod
    def _default_base_url(provider: str) -> str | None:
        if provider == "vllm":
            return os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        if provider == "kimi":
            return os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
        return os.getenv("OCTO_LLM_BASE_URL")

    @staticmethod
    def _default_api_key(provider: str) -> str | None:
        if provider == "vllm":
            return os.getenv("VLLM_API_KEY") or "not-needed-for-local-vllm"
        if provider == "kimi":
            return os.getenv("MOONSHOT_API_KEY") or os.getenv("KIMI_API_KEY")
        return os.getenv("OCTO_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

    @classmethod
    def from_env(cls) -> "LLMClient":
        return cls()

    def _openai_client(self):
        import openai

        key = ("openai", self.base_url, self.api_key)
        if key not in self._clients:
            self._clients[key] = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._clients[key]

    def _anthropic_client(self):
        import anthropic

        key = ("anthropic", self.api_key)
        if key not in self._clients:
            self._clients[key] = anthropic.Anthropic(api_key=self.api_key)
        return self._clients[key]

    def complete(self, prompt: str, system: str | None = None) -> LLMResponse:
        if self.provider in ("vllm", "kimi"):
            return self._openai_complete(prompt, system)
        if not self.api_key and self.provider in ("openai", "anthropic"):
            return self._fallback_complete(prompt, system)
        if self.provider == "openai":
            return self._openai_complete(prompt, system)
        if self.provider == "anthropic":
            return self._anthropic_complete(prompt, system)
        if self.provider == "ollama":
            return self._ollama_complete(prompt, system)
        return self._fallback_complete(prompt, system)

    def _openai_complete(self, prompt: str, system: str | None = None) -> LLMResponse:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._openai_client().chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            model=self.model,
            usage={
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
            },
        )

    def _anthropic_complete(self, prompt: str, system: str | None = None) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        resp = self._anthropic_client().messages.create(**kwargs)
        return LLMResponse(
            text=resp.content[0].text if resp.content else "",
            model=self.model,
            usage={
                "prompt_tokens": resp.usage.input_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.output_tokens if resp.usage else 0,
            },
        )

    def _ollama_complete(self, prompt: str, system: str | None = None) -> LLMResponse:
        import requests

        url = self.base_url or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        if system:
            payload["system"] = system
        resp = requests.post(f"{url}/api/generate", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(text=data.get("response", ""), model=self.model)

    def _fallback_complete(self, prompt: str, system: str | None = None) -> LLMResponse:
        """Offline fallback that returns a clear marker so callers know no LLM ran."""
        return LLMResponse(
            text=(
                "[LLM_FALLBACK] No provider configured. "
                "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, MOONSHOT_API_KEY, "
                "OLLAMA_HOST, or VLLM_BASE_URL."
            ),
            model="fallback",
        )


def is_configured() -> bool:
    """Return True if an LLM provider is configured in the environment."""
    return bool(
        os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("MOONSHOT_API_KEY")
        or os.getenv("KIMI_API_KEY")
        or os.getenv("OLLAMA_HOST")
        or os.getenv("VLLM_BASE_URL")
    )

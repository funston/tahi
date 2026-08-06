"""
Lightweight, swappable LLM client for OCTO coprocessors.

Supports OpenAI, Anthropic, Moonshot/Kimi, vLLM, and local/Ollama endpoints
via environment configuration. Falls back to a deterministic placeholder when
no backend is available so pipelines can still be tested offline.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any


class LLMNotConfiguredError(RuntimeError):
    """Raised in strict mode when no real LLM backend is available.

    Benchmarks run strict so a misconfigured run crashes instead of writing
    placeholder text into a results file, where it is indistinguishable from a
    real measurement.
    """


# USD per million tokens. Self-hosted backends (vLLM) are priced at 0 -- their
# cost is GPU-hours, which the manifest records separately as wall_clock_s.
_PRICE_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict[str, int] | None = None
    ttft_ms: float | None = None
    """Time to FIRST token, measured on a streaming call. None on non-streaming
    calls -- do not substitute total latency, which is dominated by output
    length and says nothing about prefill cost."""


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
        strict: bool | None = None,
    ):
        self.model = model or os.getenv("OCTO_LLM_MODEL", "gpt-4o")
        self.provider = (provider or os.getenv("OCTO_LLM_PROVIDER", "openai")).lower()
        self.base_url = base_url or self._default_base_url(self.provider)
        self.api_key = api_key or self._default_api_key(self.provider)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._clients: dict[str, Any] = {}
        # Strict mode forbids silent degradation. Every measurement path sets it.
        if strict is None:
            strict = os.getenv("OCTO_STRICT", "").strip().lower() in ("1", "true", "yes")
        self.strict = strict
        # Observability: callers can assert no fallback was used.
        self.fallback_calls = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_calls = 0

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
        prompt_tokens = resp.usage.prompt_tokens if resp.usage else 0
        completion_tokens = resp.usage.completion_tokens if resp.usage else 0
        self._record(prompt_tokens, completion_tokens)
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            model=self.model,
            usage={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        )

    def complete_streaming(self, prompt: str, system: str | None = None) -> LLMResponse:
        """Complete with a real time-to-first-token measurement.

        Stops the clock on the first chunk carrying non-empty content. This is
        the only honest way to measure TTFT: total wall-clock on a non-streaming
        call scales with output length, so a system that answers more tersely
        looks "faster" at prefill when nothing about prefill changed.
        """
        if self.provider not in ("vllm", "kimi", "openai"):
            raise NotImplementedError(
                f"Streaming TTFT is implemented for OpenAI-compatible providers; got {self.provider!r}."
            )
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        start = time.perf_counter()
        stream = self._openai_client().chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )

        ttft_ms: float | None = None
        chunks: list[str] = []
        prompt_tokens = completion_tokens = 0
        for chunk in stream:
            if getattr(chunk, "usage", None):
                prompt_tokens = chunk.usage.prompt_tokens or 0
                completion_tokens = chunk.usage.completion_tokens or 0
            if not chunk.choices:
                continue
            piece = chunk.choices[0].delta.content
            if piece:
                if ttft_ms is None:
                    ttft_ms = (time.perf_counter() - start) * 1000.0
                chunks.append(piece)

        text = "".join(chunks)
        if not completion_tokens:
            completion_tokens = len(text.split())
        self._record(prompt_tokens, completion_tokens)
        return LLMResponse(
            text=text,
            model=self.model,
            usage={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            ttft_ms=ttft_ms,
        )

    def _record(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.total_calls += 1
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens

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
        """Offline fallback that returns a clear marker so callers know no LLM ran.

        In strict mode this raises instead. Benchmarks run strict, so a
        misconfigured run crashes rather than writing placeholder text into a
        results file where it is indistinguishable from a real measurement.
        """
        if self.strict:
            raise LLMNotConfiguredError(
                f"No LLM provider configured (provider={self.provider!r}, model={self.model!r}) "
                "and strict mode is enabled. Refusing to emit placeholder text into a "
                "measurement path. Set OCTO_LLM_PROVIDER and the matching credentials, "
                "or construct LLMClient(strict=False) for demo use."
            )
        self.fallback_calls += 1
        return LLMResponse(
            text=(
                "[LLM_FALLBACK] No provider configured. "
                "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, MOONSHOT_API_KEY, "
                "OLLAMA_HOST, or VLLM_BASE_URL."
            ),
            model="fallback",
        )

    def usage_summary(self) -> dict[str, Any]:
        """Token and cost accounting for the run manifest.

        `cost_per_correct_answer` is the number that decides whether OCTO is
        commercially viable, and it cannot be computed without this.
        """
        pricing = _PRICE_PER_MTOK.get(self.model, {})
        cost = (
            self.total_prompt_tokens / 1e6 * pricing.get("input", 0.0)
            + self.total_completion_tokens / 1e6 * pricing.get("output", 0.0)
        )
        return {
            "provider": self.provider,
            "model": self.model,
            "total_calls": self.total_calls,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "fallback_calls": self.fallback_calls,
            "est_cost_usd": round(cost, 4),
            "cost_basis": "known-price" if pricing else "unpriced-or-self-hosted",
        }


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

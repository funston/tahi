"""Tests for the swappable LLM client."""



from tahi.llm_client import LLMClient, is_configured


def _clear_env(monkeypatch):
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OLLAMA_HOST",
        "MOONSHOT_API_KEY",
        "KIMI_API_KEY",
        "VLLM_BASE_URL",
        "VLLM_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_llm_client_fallback_without_key(monkeypatch):
    """When no provider key is present, the client returns a clear fallback marker."""
    _clear_env(monkeypatch)

    client = LLMClient.from_env()
    resp = client.complete("What is 2+2?")
    assert "LLM_FALLBACK" in resp.text
    assert resp.model == "fallback"


def test_is_configured_false_without_key(monkeypatch):
    _clear_env(monkeypatch)
    assert is_configured() is False


def test_is_configured_true_for_vllm(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    assert is_configured() is True


def test_is_configured_true_for_kimi(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-test")
    assert is_configured() is True


def test_vllm_provider_uses_openai_client_and_local_defaults(monkeypatch):
    """vllm provider routes through the OpenAI-compatible client with local defaults."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("TAHI_LLM_PROVIDER", "vllm")
    monkeypatch.setenv("TAHI_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")

    client = LLMClient.from_env()
    assert client.provider == "vllm"
    assert client.base_url == "http://localhost:8000/v1"
    assert client.api_key == "not-needed-for-local-vllm"


def test_kimi_provider_uses_moonshot_defaults(monkeypatch):
    """kimi provider routes to Moonshot's OpenAI-compatible endpoint."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("TAHI_LLM_PROVIDER", "kimi")
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-test")

    client = LLMClient.from_env()
    assert client.provider == "kimi"
    assert client.base_url == "https://api.moonshot.cn/v1"
    assert client.api_key == "sk-test"

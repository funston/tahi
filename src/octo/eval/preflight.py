"""
Preflight checks: fail loudly, before a run, on anything that would silently
degrade the result.

The rule this enforces: a missing package, an unloadable model, or an occupied
GPU must stop the run at startup with a specific message. It must never be
absorbed by a `try/except` that substitutes a weaker component and carries on,
because the resulting artifact is indistinguishable from a real measurement.

Three real instances this repo hit, all of which this module now catches:

  1. `sentence-transformers` imports `torchcodec`, which needs FFmpeg shared
     libraries. Missing libs raised at import time, `get_encoder()` caught it,
     and every "dense retrieval" number was actually a character-sum hash.
  2. `LLMClient` returned placeholder text when no provider was configured,
     producing a full results file of zeros that was then published.
  3. A vLLM server holding 115 GB of a 130 GB GPU made every in-process CUDA
     allocation fail; the harness labelled it "CUDA memory allocation skipped"
     and ran on CPU, reporting `peak_vram_gb: 0.00` as though that were normal.

Usage:
    from octo.eval.preflight import require_ready
    env = require_ready(need_llm=True, need_encoder=True)
"""

from __future__ import annotations

import importlib
import shutil
from dataclasses import dataclass, field
from typing import Any


class PreflightError(RuntimeError):
    """A dependency or resource needed for a valid measurement is unavailable."""


@dataclass
class Environment:
    """What is actually available. Every field goes into the run manifest."""

    encoder_name: str = ""
    encoder_dim: int = 0
    encoder_device: str = ""
    llm_provider: str = ""
    llm_model: str = ""
    cuda_available: bool = False
    cuda_device: str = ""
    cuda_free_gb: float = 0.0
    cuda_total_gb: float = 0.0
    packages: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "encoder": self.encoder_name,
            "encoder_dim": self.encoder_dim,
            "encoder_device": self.encoder_device,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "cuda_available": self.cuda_available,
            "cuda_device": self.cuda_device,
            "cuda_free_gb": round(self.cuda_free_gb, 2),
            "cuda_total_gb": round(self.cuda_total_gb, 2),
            "packages": self.packages,
            "warnings": self.warnings,
        }


# (import name, pip name, what breaks without it)
REQUIRED_PACKAGES: list[tuple[str, str, str]] = [
    ("torch", "torch", "GCCA adapters and all native Level 2/3 work"),
    ("numpy", "numpy", "vector operations throughout retrieval"),
]
RETRIEVAL_PACKAGES: list[tuple[str, str, str]] = [
    ("sentence_transformers", "sentence-transformers", "real dense embeddings"),
    ("faiss", "faiss-cpu", "approximate nearest-neighbour search"),
]


def check_packages(specs: list[tuple[str, str, str]]) -> tuple[dict[str, str], list[str]]:
    """Import each package. Returns (versions, problems) -- never raises."""
    versions: dict[str, str] = {}
    problems: list[str] = []
    for import_name, pip_name, why in specs:
        try:
            mod = importlib.import_module(import_name)
            versions[pip_name] = getattr(mod, "__version__", "unknown")
        except Exception as exc:  # noqa: BLE001 -- reported, never swallowed
            problems.append(
                f"{pip_name!r} is unavailable ({type(exc).__name__}: {exc}).\n"
                f"      Needed for: {why}\n"
                f"      Fix: pip install {pip_name}"
            )
    return versions, problems


def check_ffmpeg_for_torchcodec() -> list[str]:
    """`sentence-transformers` >= 5.x imports torchcodec, which needs FFmpeg.

    Reported explicitly because the failure surfaces as an opaque
    `OSError: libavutil.so.NN: cannot open shared object file` deep inside an
    import chain that has nothing to do with text embedding.
    """
    try:
        importlib.import_module("torchcodec")
    except ModuleNotFoundError:
        return []  # not installed at all -- sentence-transformers guards this
    except Exception as exc:  # noqa: BLE001
        if shutil.which("ffmpeg") is None:
            return [
                f"'torchcodec' is installed but cannot load ({type(exc).__name__}), "
                "and no FFmpeg is present.\n"
                "      This breaks `import sentence_transformers` entirely.\n"
                "      Fix: `pip uninstall torchcodec` (OCTO uses no audio/video), "
                "or install FFmpeg (`apt install ffmpeg`)."
            ]
        return [f"'torchcodec' failed to load: {type(exc).__name__}: {exc}"]
    return []


def check_cuda(min_free_gb: float = 2.0) -> tuple[dict[str, Any], list[str]]:
    """Report GPU state. An occupied GPU is a warning, never a silent CPU switch."""
    info: dict[str, Any] = {
        "cuda_available": False, "cuda_device": "",
        "cuda_free_gb": 0.0, "cuda_total_gb": 0.0,
    }
    warnings: list[str] = []
    try:
        import torch

        if not torch.cuda.is_available():
            return info, ["CUDA is not available; native Level 2/3 work cannot run."]
        info["cuda_available"] = True
        info["cuda_device"] = torch.cuda.get_device_name(0)
        free, total = torch.cuda.mem_get_info()
        info["cuda_free_gb"] = free / 1e9
        info["cuda_total_gb"] = total / 1e9
        if info["cuda_free_gb"] < min_free_gb:
            warnings.append(
                f"Only {info['cuda_free_gb']:.1f} GB free of "
                f"{info['cuda_total_gb']:.1f} GB on {info['cuda_device']}.\n"
                "      Almost certainly a vLLM server holding its KV-cache arena "
                "(default --gpu-memory-utilization is 0.90).\n"
                "      A small model failing to allocate here is NOT a model-size "
                "problem -- do not 'fix' it by falling back to CPU.\n"
                "      Fix: restart vLLM with a lower GPU_MEM_UTIL "
                "(scripts/start_vllm_server.sh), or stop it while running "
                "in-process native work."
            )
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Could not query CUDA: {type(exc).__name__}: {exc}")
    return info, warnings


def require_ready(
    *,
    need_llm: bool = True,
    need_encoder: bool = True,
    need_cuda: bool = False,
    encoder_device: str | None = None,
) -> Environment:
    """Verify everything needed for a valid run, or raise with all problems at once.

    Reports every problem together rather than failing on the first, so a
    misconfigured machine takes one fix cycle instead of five.
    """
    env = Environment()
    problems: list[str] = []

    versions, probs = check_packages(REQUIRED_PACKAGES)
    env.packages.update(versions)
    problems.extend(probs)

    if need_encoder:
        problems.extend(check_ffmpeg_for_torchcodec())
        versions, probs = check_packages(RETRIEVAL_PACKAGES)
        env.packages.update(versions)
        problems.extend(probs)

    cuda_info, cuda_warnings = check_cuda()
    env.cuda_available = cuda_info["cuda_available"]
    env.cuda_device = cuda_info["cuda_device"]
    env.cuda_free_gb = cuda_info["cuda_free_gb"]
    env.cuda_total_gb = cuda_info["cuda_total_gb"]
    if need_cuda:
        problems.extend(cuda_warnings)
    else:
        env.warnings.extend(cuda_warnings)

    # Load the real encoder. An explicit device choice is fine and gets recorded;
    # a silent substitution of a weaker encoder is not.
    if need_encoder and not problems:
        device = encoder_device or ("cpu" if env.cuda_free_gb < 2.0 else "cuda")
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
            env.encoder_name = "sentence-transformers/all-MiniLM-L6-v2"
            env.encoder_dim = model.get_sentence_embedding_dimension()
            env.encoder_device = device
            if device == "cpu" and env.cuda_available:
                env.warnings.append(
                    "Encoder pinned to CPU because the GPU is occupied. This is "
                    "recorded, not silent -- embeddings are still real."
                )
        except Exception as exc:  # noqa: BLE001
            problems.append(
                f"Real encoder failed to load on device={device!r} "
                f"({type(exc).__name__}: {exc}).\n"
                "      Refusing to substitute the hash encoder: retrieval numbers "
                "from it are meaningless."
            )

    if need_llm:
        from octo.llm_client import LLMClient

        client = LLMClient(strict=True)
        env.llm_provider = client.provider
        env.llm_model = client.model
        if not client.api_key and client.provider in ("openai", "anthropic"):
            problems.append(
                f"No credentials for LLM provider {client.provider!r}.\n"
                "      Fix: set OCTO_LLM_PROVIDER + the matching API key, or point "
                "OCTO_LLM_PROVIDER=vllm at a running server."
            )

    if problems:
        raise PreflightError(
            "Preflight failed -- refusing to start a run that would produce "
            "invalid results:\n\n  - " + "\n\n  - ".join(problems)
        )
    return env


if __name__ == "__main__":
    import json

    try:
        env = require_ready(need_llm=False, need_encoder=True)
        print("PREFLIGHT OK")
        print(json.dumps(env.to_dict(), indent=2))
    except PreflightError as exc:
        print(exc)
        raise SystemExit(1)

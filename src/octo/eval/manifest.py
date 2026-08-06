"""
Run manifests: every result artifact self-describes how it was produced.

The failure this prevents: a benchmark JSON with plausible-looking numbers and
no way to tell whether a real model answered, which encoder ran, or what code
produced it. `encoder_is_fallback` and `strict_mode` are on the face of every
artifact for exactly that reason -- a degraded run is visible without having to
reason about the numbers.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return "unknown"


def git_sha() -> str:
    return _git("rev-parse", "--short", "HEAD")


def git_dirty() -> bool:
    return bool(_git("status", "--porcelain"))


def sha256_of(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_of_obj(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


@dataclass
class RunManifest:
    """Provenance for one benchmark run. Required on every result artifact."""

    benchmark: str
    dataset: str
    dataset_sha256: str = ""
    n_items: int = 0
    seed: int = 0

    git_sha: str = field(default_factory=git_sha)
    git_dirty: bool = field(default_factory=git_dirty)
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    python: str = field(default_factory=lambda: sys.version.split()[0])
    platform: str = field(default_factory=platform.platform)

    provider: str = ""
    model: str = ""
    judge_model: str = ""
    """Pinned judge model. An LLM-judged metric is not reproducible across judge
    versions, so the judge is part of the experiment, not an implementation
    detail."""

    encoder: str = ""
    encoder_is_fallback: bool = False
    """True if the real sentence-transformer failed to load and a hash encoder
    was substituted. A run with this set to True is not a retrieval result."""

    strict_mode: bool = False
    wall_clock_s: float = 0.0
    llm_usage: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def validate(self) -> None:
        """Refuse to stamp an artifact that is not a real measurement."""
        problems = []
        if not self.strict_mode:
            problems.append("strict_mode is False -- silent fallbacks were possible")
        if self.encoder_is_fallback:
            problems.append("encoder_is_fallback is True -- hash encoder, not embeddings")
        if self.llm_usage.get("fallback_calls"):
            problems.append(
                f"{self.llm_usage['fallback_calls']} LLM calls returned placeholder text"
            )
        if self.n_items == 0:
            problems.append("n_items is 0")
        if problems:
            raise ValueError(
                "Refusing to write a results artifact from a degraded run:\n  - "
                + "\n  - ".join(problems)
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def encoder_is_fallback() -> bool:
    """True if get_encoder() would silently return the hash encoder.

    Checked before a run rather than after, so a missing sentence-transformer
    model is a startup failure instead of a subtly wrong result set.
    """
    try:
        from octo.retrieval.ann import STEncoder

        STEncoder()
        return False
    except Exception:
        return True


def write_artifact(
    path: str | Path,
    manifest: RunManifest,
    payload: dict[str, Any],
    *,
    allow_degraded: bool = False,
) -> Path:
    """Write a results JSON with its manifest attached.

    Validates the manifest first: a degraded run raises rather than producing a
    file that looks like every other file in the directory.
    """
    if not allow_degraded:
        manifest.validate()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"manifest": manifest.to_dict(), **payload}, indent=2, default=str),
        encoding="utf-8",
    )
    return out

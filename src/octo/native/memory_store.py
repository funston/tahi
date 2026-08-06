"""
Precomputed GCCA memory vectors, shared verbatim by training and evaluation.

The defect that voided the 2026-08-03 L3 run was an asymmetry between how
training built its memory tensor and how evaluation built its. `train_gcca.py`
encoded `memory_texts` with SentenceTransformer directly; `run_l3_native.py`
routed the same texts through `build_memory_tensor`, and -- once the RGAT
landed -- through a randomly-initialised graph encoder as well. The adapter was
trained on one distribution and scored on another. Both paths were *supposed*
to agree, and nothing checked that they did, so the measured -0.0117 token-F1
delta described the mismatch rather than the architecture.

This module removes the possibility rather than documenting it. Memory vectors
are computed once, written to a single `.npz`, and read back by both sides.
Symmetry becomes a property of the bytes on disk instead of two code paths
staying in sync across future edits.

The store also carries the provenance needed to interpret a run: which encoder
produced the vectors, whether they came from retrieval or from gold documents,
and whether a graph encoder was in the path. `run_l3_native.py` copies this
into the run manifest, so a result can never again be reported without stating
what filled its memory.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch

# Bumped when the on-disk layout changes in a way older readers cannot handle.
STORE_FORMAT_VERSION = 1

# Keys every store must carry. `load_memory_store` refuses a store missing any
# of them -- an unlabelled memory store is exactly how the last run became
# uninterpretable.
REQUIRED_META = ("format_version", "memory_source", "encoder", "d_model",
                 "max_slots", "gnn", "n_questions")


class MemoryStoreError(RuntimeError):
    """Raised when a store is absent, malformed, or missing provenance."""


def _vectors_sha256(vectors: dict[str, np.ndarray]) -> str:
    """Content hash over the vectors themselves, in question-id order.

    Recorded in both the training manifest and the benchmark manifest. If the
    two differ, training and evaluation did not see the same memory and the
    comparison is void -- which is the failure this module exists to catch.
    """
    h = hashlib.sha256()
    for qid in sorted(vectors):
        h.update(qid.encode("utf-8"))
        h.update(np.ascontiguousarray(vectors[qid], dtype=np.float32).tobytes())
    return h.hexdigest()


class MemoryStore:
    """Read-only view over precomputed per-question memory slots."""

    def __init__(self, vectors: dict[str, np.ndarray], meta: dict[str, Any]):
        self._vectors = vectors
        self.meta = meta
        self.sha256 = meta.get("vectors_sha256") or _vectors_sha256(vectors)

    def __len__(self) -> int:
        return len(self._vectors)

    def __contains__(self, question_id: str) -> bool:
        return question_id in self._vectors

    @property
    def question_ids(self) -> list[str]:
        return sorted(self._vectors)

    @property
    def d_model(self) -> int:
        return int(self.meta["d_model"])

    def slots(self, question_id: str) -> np.ndarray | None:
        """Raw `[K, d]` slots for a question, or None if it has no memory."""
        v = self._vectors.get(question_id)
        return None if v is None else np.asarray(v, dtype=np.float32)

    def tensor(
        self,
        question_id: str,
        *,
        device: str | torch.device = "cpu",
        dtype: torch.dtype = torch.float32,
    ) -> torch.Tensor | None:
        """`[1, K, d]` memory tensor for a question, shaped for GCCA.

        This is the only conversion either side performs. Training and
        evaluation call it with the same `question_id` and receive identical
        values by construction.
        """
        slots = self.slots(question_id)
        if slots is None or slots.size == 0:
            return None
        if slots.ndim == 1:
            slots = slots[None, :]
        return torch.from_numpy(np.ascontiguousarray(slots)).to(
            device=device, dtype=dtype
        ).unsqueeze(0)


def save_memory_store(
    path: str | Path,
    vectors: dict[str, np.ndarray],
    meta: dict[str, Any],
) -> str:
    """Write vectors plus provenance. Returns the content hash.

    Slots are stored per question because K varies (a question with two gold
    documents has two slots). Padding to a common K here would silently teach
    the adapter to attend over zero vectors.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    arrays: dict[str, np.ndarray] = {}
    dims: set[int] = set()
    for qid, v in vectors.items():
        arr = np.ascontiguousarray(np.asarray(v, dtype=np.float32))
        if arr.ndim == 1:
            arr = arr[None, :]
        if arr.ndim != 2:
            raise MemoryStoreError(
                f"Memory for {qid!r} has shape {arr.shape}; expected [K, d]."
            )
        dims.add(arr.shape[1])
        arrays[qid] = arr

    if len(dims) > 1:
        raise MemoryStoreError(
            f"Inconsistent embedding dimensions across questions: {sorted(dims)}."
        )

    full_meta = dict(meta)
    full_meta["format_version"] = STORE_FORMAT_VERSION
    full_meta["n_questions"] = len(arrays)
    full_meta["d_model"] = int(next(iter(dims))) if dims else 0
    full_meta["vectors_sha256"] = _vectors_sha256(arrays)

    missing = [k for k in REQUIRED_META if k not in full_meta]
    if missing:
        raise MemoryStoreError(f"Memory store meta is missing {missing}.")

    np.savez_compressed(path, __meta__=np.array(json.dumps(full_meta)), **arrays)
    return full_meta["vectors_sha256"]


def load_memory_store(path: str | Path) -> MemoryStore:
    """Load a store, refusing anything without complete provenance."""
    path = Path(path)
    if not path.exists():
        raise MemoryStoreError(
            f"Memory store not found: {path}. Build it with "
            "`scripts/build_gcca_training_data.py --memory-source oracle`."
        )

    with np.load(path, allow_pickle=False) as npz:
        keys = [k for k in npz.files if k != "__meta__"]
        if "__meta__" not in npz.files:
            raise MemoryStoreError(
                f"{path} carries no `__meta__`. A store without provenance cannot "
                "be used -- the run manifest would not record what filled memory."
            )
        meta = json.loads(str(npz["__meta__"].item()))
        vectors = {k: np.asarray(npz[k], dtype=np.float32) for k in keys}

    missing = [k for k in REQUIRED_META if k not in meta]
    if missing:
        raise MemoryStoreError(f"{path} meta is missing {missing}.")

    if int(meta["format_version"]) != STORE_FORMAT_VERSION:
        raise MemoryStoreError(
            f"{path} is format v{meta['format_version']}; this build reads "
            f"v{STORE_FORMAT_VERSION}."
        )

    recomputed = _vectors_sha256(vectors)
    if meta.get("vectors_sha256") != recomputed:
        raise MemoryStoreError(
            f"{path} content hash mismatch: meta says {meta.get('vectors_sha256')}, "
            f"vectors hash to {recomputed}. The file has been modified."
        )
    return MemoryStore(vectors, meta)


def assert_symmetric(train_store: MemoryStore, eval_store: MemoryStore) -> None:
    """Fail loudly if the two sides are not the same memory.

    Called by both `train_gcca.py` and `run_l3_native.py` when a store is used.
    A same-path assertion is cheap; the alternative is another run whose delta
    measures a representation mismatch.
    """
    if train_store.sha256 != eval_store.sha256:
        raise MemoryStoreError(
            "Train and eval memory stores differ "
            f"({train_store.sha256[:12]} vs {eval_store.sha256[:12]}). "
            "The L3 comparison would be void."
        )


def encode_texts(encoder: Any, texts: Iterable[str]) -> np.ndarray:
    """Encode and L2-normalise `[K, d]`. The single encoding path for stores.

    Normalisation matches `build_memory_tensor`, so a retrieved-source store is
    numerically interchangeable with the live retrieval path.
    """
    texts = list(texts)
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    vecs = np.asarray(encoder.encode(texts), dtype=np.float32)
    if vecs.ndim == 1:
        vecs = vecs[None, :]
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return np.ascontiguousarray(vecs / np.clip(norms, 1e-8, None))

#!/usr/bin/env python
"""
Train GCCA adapters on a frozen base model.

Trains ONLY `W_K`, `W_V`, and the gate `alpha` inside each
`GatedChunkedCrossAttention` block. Every base-model parameter stays frozen, so
this cannot cause catastrophic forgetting and the trainable footprint stays
around 1-2% of the model.

Why this is the load-bearing step for Level 3: `alpha` is zero-initialised, so
`h + tanh(0) * attn == h` exactly. Until `alpha` moves off zero, the adapter is
a mathematical identity and Level 3 is indistinguishable from the base model.
Training is not an optimisation here -- it is what makes the feature exist.

Loss is standard next-token cross-entropy on the ANSWER tokens only; prompt
tokens are masked out with -100 so the model is not rewarded for reproducing
the question or the retrieved evidence.

Usage:
    python scripts/train_gcca.py \
        --model Qwen/Qwen2.5-1.5B-Instruct \
        --data data/gcca_train.jsonl \
        --output checkpoints/gcca \
        --epochs 3

Training data format (JSONL), one record per line:
    {"query": "...", "answer": "...", "memory_texts": ["doc text", "..."]}

`memory_texts` are the retrieved node texts for that query -- produce them with
`octo.native.memory.node_texts` so training and inference see the same shape.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from octo.native.huggingface_adapter import OctoNativeAdapter  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("octo.train_gcca")

PROMPT_TEMPLATE = "QUESTION: {query}\nANSWER:"


class GCCADataset(Dataset):
    """Query/answer pairs plus the encoded memory slots for each."""

    def __init__(self, path: str | Path, tokenizer, encoder, max_slots: int,
                 max_length: int = 1024, memory_store=None):
        self.rows: list[dict] = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    self.rows.append(json.loads(line))
        if not self.rows:
            raise ValueError(f"No training records in {path}")
        self.tok = tokenizer
        self.encoder = encoder
        self.max_slots = max_slots
        self.max_length = max_length
        self.memory_store = memory_store
        log.info("Loaded %d training records from %s", len(self.rows), path)

        if memory_store is not None:
            missing = [r["question_id"] for r in self.rows
                       if r["question_id"] not in memory_store]
            if missing:
                raise ValueError(
                    f"{len(missing)} records in {path} have no entry in the memory "
                    f"store (first: {missing[0]}). Training would silently fall back "
                    "to a different memory representation than evaluation uses -- "
                    "the exact asymmetry that voided the 2026-08-03 run."
                )
            log.info("Memory from store: %d questions, d=%d, source=%s, sha=%s",
                     len(memory_store), memory_store.d_model,
                     memory_store.meta.get("memory_source"),
                     memory_store.sha256[:16])

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> dict:
        row = self.rows[idx]
        prompt = PROMPT_TEMPLATE.format(query=row["query"])
        answer = " " + row["answer"].strip()

        prompt_ids = self.tok(prompt, add_special_tokens=True)["input_ids"]
        answer_ids = self.tok(answer, add_special_tokens=False)["input_ids"]
        input_ids = (prompt_ids + answer_ids)[: self.max_length]

        # -100 masks a position out of the loss. Only answer tokens are learned;
        # rewarding reproduction of the prompt teaches copying, not grounding.
        labels = ([-100] * len(prompt_ids) + answer_ids)[: self.max_length]

        # Precomputed store is authoritative when present: evaluation reads the
        # same bytes, so the adapter cannot be trained on one representation and
        # scored on another.
        if self.memory_store is not None:
            vecs = self.memory_store.slots(row["question_id"])
            if vecs is None or vecs.size == 0:
                vecs = np.zeros((1, self.memory_store.d_model), dtype=np.float32)
            else:
                vecs = vecs[: self.max_slots]
        else:
            texts = (row.get("memory_texts") or [])[: self.max_slots]
            if texts:
                vecs = np.asarray(self.encoder.encode(texts), dtype=np.float32)
                if vecs.ndim == 1:
                    vecs = vecs[None, :]
                vecs = vecs / np.clip(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-8, None)
            else:
                vecs = np.zeros((1, self.encoder.dimension), dtype=np.float32)
        vecs = np.ascontiguousarray(vecs, dtype=np.float32)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
            "memory": torch.from_numpy(vecs),
        }


def collate(batch: list[dict], pad_id: int) -> dict:
    """Right-pad sequences and memory slots to the batch maximum."""
    max_len = max(b["input_ids"].size(0) for b in batch)
    max_slots = max(b["memory"].size(0) for b in batch)
    d = batch[0]["memory"].size(1)

    input_ids = torch.full((len(batch), max_len), pad_id, dtype=torch.long)
    labels = torch.full((len(batch), max_len), -100, dtype=torch.long)
    attn = torch.zeros((len(batch), max_len), dtype=torch.long)
    memory = torch.zeros((len(batch), max_slots, d), dtype=torch.float32)

    for i, b in enumerate(batch):
        n = b["input_ids"].size(0)
        input_ids[i, :n] = b["input_ids"]
        labels[i, :n] = b["labels"]
        attn[i, :n] = 1
        k = b["memory"].size(0)
        memory[i, :k] = b["memory"]

    return {"input_ids": input_ids, "labels": labels,
            "attention_mask": attn, "memory": memory}


def trainable_report(adapter: OctoNativeAdapter) -> tuple[int, int]:
    trainable = sum(p.numel() for p in adapter.parameters() if p.requires_grad)
    total = sum(p.numel() for p in adapter.parameters())
    return trainable, total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="HF model id or local path")
    ap.add_argument("--data", required=True, help="Training JSONL")
    ap.add_argument("--eval-data", default=None, help="Optional held-out JSONL")
    ap.add_argument("--output", default="checkpoints/gcca")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--warmup", type=int, default=50)
    ap.add_argument("--max-slots", type=int, default=16)
    ap.add_argument("--max-length", type=int, default=1024)
    ap.add_argument("--interleave-step", type=int, default=4,
                    help="Attach a GCCA block every N transformer layers")
    ap.add_argument("--encoder", default="all-MiniLM-L6-v2")
    ap.add_argument("--memory-store", default=None,
                    help="Precomputed memory_vectors.npz. Strongly recommended: "
                         "evaluation reads the same file, which is what makes the "
                         "train/eval memory representation provably identical.")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--grad-clip", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    from sentence_transformers import SentenceTransformer
    from transformers import AutoModelForCausalLM, AutoTokenizer

    log.info("Loading base model %s", args.model)
    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.float32, device_map=None,
    ).to(args.device)
    base.config.use_cache = False

    st = SentenceTransformer(args.encoder, device=args.device)

    class _Enc:
        dimension = st.get_sentence_embedding_dimension()

        @staticmethod
        def encode(texts):
            return st.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    store = None
    if args.memory_store:
        from octo.native.memory_store import load_memory_store
        store = load_memory_store(args.memory_store)
        if store.d_model != _Enc.dimension:
            log.error("Memory store is d=%d but encoder %r is d=%d. The store was "
                      "built with a different encoder; GCCA projections would be "
                      "the wrong shape.", store.d_model, args.encoder, _Enc.dimension)
            return 1
    else:
        log.warning("No --memory-store: memory will be re-encoded here and must be "
                    "re-encoded identically at eval time. Prefer a store.")

    adapter = OctoNativeAdapter(
        base_model=base,
        d_retriever=_Enc.dimension,
        interleave_step=args.interleave_step,
    ).to(args.device)

    trainable, total = trainable_report(adapter)
    log.info("Trainable %s / %s params (%.2f%%) -- base model frozen",
             f"{trainable:,}", f"{total:,}", 100 * trainable / max(total, 1))
    if trainable == 0:
        log.error("No trainable parameters. GCCA blocks were not attached.")
        return 1

    ds = GCCADataset(args.data, tok, _Enc, args.max_slots, args.max_length)
    dl = DataLoader(ds, batch_size=args.batch_size, shuffle=True,
                    collate_fn=lambda b: collate(b, tok.pad_token_id))
    eval_dl = None
    if args.eval_data:
        eds = GCCADataset(args.eval_data, tok, _Enc, args.max_slots, args.max_length)
        eval_dl = DataLoader(eds, batch_size=args.batch_size, shuffle=False,
                             collate_fn=lambda b: collate(b, tok.pad_token_id))

    params = [p for p in adapter.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.01)
    steps = max(1, len(dl) * args.epochs)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, s / max(1, args.warmup))
                       * 0.5 * (1 + math.cos(math.pi * min(1.0, s / steps))),
    )

    alpha0 = [g.alpha.detach().clone() for g in adapter.gcca_layers.values()]
    log.info("alpha at init: %s (identity -- adapter is inert until this moves)",
             [round(float(a), 6) for a in alpha0])

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    step = 0

    for epoch in range(args.epochs):
        adapter.train()
        running = 0.0
        for batch in dl:
            input_ids = batch["input_ids"].to(args.device)
            labels = batch["labels"].to(args.device)
            attn = batch["attention_mask"].to(args.device)
            memory = batch["memory"].to(args.device)

            adapter.set_retrieved_memory(memory)
            out = adapter(input_ids=input_ids, attention_mask=attn)
            logits = out.logits if hasattr(out, "logits") else out[0]

            # Standard causal shift: position t predicts token t+1.
            shift_logits = logits[:, :-1, :].contiguous()
            shift_labels = labels[:, 1:].contiguous()
            loss = F.cross_entropy(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1),
                ignore_index=-100,
            )

            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, args.grad_clip)
            opt.step()
            sched.step()
            adapter.clear_retrieved_memory()

            running += loss.item()
            step += 1
            if step % 20 == 0:
                alphas = [round(float(torch.tanh(g.alpha)), 5)
                          for g in adapter.gcca_layers.values()]
                log.info("epoch %d step %d loss %.4f tanh(alpha) %s",
                         epoch, step, running / 20, alphas)
                running = 0.0

        if eval_dl is not None:
            adapter.eval()
            tot, n = 0.0, 0
            with torch.no_grad():
                for batch in eval_dl:
                    adapter.set_retrieved_memory(batch["memory"].to(args.device))
                    out = adapter(input_ids=batch["input_ids"].to(args.device),
                                  attention_mask=batch["attention_mask"].to(args.device))
                    logits = out.logits if hasattr(out, "logits") else out[0]
                    lbl = batch["labels"].to(args.device)
                    tot += F.cross_entropy(
                        logits[:, :-1].reshape(-1, logits.size(-1)),
                        lbl[:, 1:].reshape(-1), ignore_index=-100).item()
                    n += 1
                    adapter.clear_retrieved_memory()
            log.info("epoch %d eval loss %.4f (ppl %.2f)", epoch, tot / n,
                     math.exp(min(20, tot / n)))

        ckpt = out_dir / f"gcca_epoch{epoch}.pt"
        torch.save({
            "gcca_state_dict": adapter.gcca_layers.state_dict(),
            "d_retriever": _Enc.dimension,
            "interleave_step": args.interleave_step,
            "base_model": args.model,
            "encoder": args.encoder,
            "epoch": epoch,
            # Recorded so the benchmark can refuse to score this checkpoint
            # against memory it was not trained on.
            "memory_store": args.memory_store,
            "memory_store_sha256": store.sha256 if store is not None else None,
        }, ckpt)
        log.info("Saved %s", ckpt)

    alphas = [float(torch.tanh(g.alpha)) for g in adapter.gcca_layers.values()]
    moved = max(abs(a) for a in alphas)
    log.info("Training finished in %.1fs. Final tanh(alpha): %s",
             time.perf_counter() - started, [round(a, 5) for a in alphas])

    if moved < 1e-4:
        log.error(
            "alpha never moved off zero -- the adapter is still an identity "
            "function and Level 3 remains inert. Check that gradients reach the "
            "GCCA blocks and that memory slots are non-degenerate."
        )
        return 1
    log.info("alpha moved off zero (max |tanh(alpha)| = %.5f): the adapter is "
             "now a live component.", moved)
    return 0


if __name__ == "__main__":
    sys.exit(main())

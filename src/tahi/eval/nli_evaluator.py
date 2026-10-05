"""
NLI (Natural Language Inference) Entailment & Contradiction Evaluator.

Replaces lexical groundedness (Defect D8) with a polarity-aware, deterministic
NLI cross-encoder model (e.g. `cross-encoder/nli-deberta-v3-base` or `roberta-large-mnli`).

Metrics:
  p_entailment     Probability evidence logically entails claim.
  p_contradiction  Probability evidence directly contradicts claim (captures negations & numeric swaps).
  truth_score      p_entailment - p_contradiction  (range -1.0 to +1.0).
"""

from __future__ import annotations

from collections.abc import Sequence

import torch

try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
except ImportError:
    AutoTokenizer = None
    AutoModelForSequenceClassification = None


class NLIEvaluator:
    """Deterministic NLI Evaluator for claim truthfulness and contradiction detection."""

    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-base", device: str | None = None):
        if AutoTokenizer is None or AutoModelForSequenceClassification is None:
            raise ImportError("transformers is not installed. `pip install transformers`.")

        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.device)
        self.model.eval()

        # Map model label IDs to entailment/neutral/contradiction
        id2label = getattr(self.model.config, "id2label", {})
        self.label_map = {idx: str(label).lower() for idx, label in id2label.items()}

    def _chunk_text(self, text: str, max_words: int = 200) -> list[str]:
        """Split evidence text into passages of ~200 words to fit NLI token windows."""
        words = text.split()
        if len(words) <= max_words:
            return [text]
        chunks = []
        for i in range(0, len(words), max_words):
            chunks.append(" ".join(words[i: i + max_words]))
        return chunks

    def score_pair(self, evidence: str, claim: str) -> dict[str, float]:
        """Score pair (evidence, claim) across passage chunks using Max-Pooling aggregation.

        Prevents 512-token truncation blindness: long evidence contexts are split into
        passages and scored independently. Max-entailment and max-contradiction are extracted.
        """
        if not evidence.strip() or not claim.strip():
            return {"entailment": 0.0, "neutral": 1.0, "contradiction": 0.0, "truth_score": 0.0}

        passages = self._chunk_text(evidence, max_words=200)
        max_entail = 0.0
        max_contra = 0.0
        best_neutral = 1.0

        for passage in passages:
            inputs = self.tokenizer(passage, claim, return_tensors="pt", truncation=True, max_length=512).to(self.device)
            with torch.no_grad():
                logits = self.model(**inputs).logits
                probs = torch.softmax(logits, dim=-1).squeeze(0).tolist()

            p_ent, p_neu, p_con = 0.0, 0.0, 0.0
            for idx, prob in enumerate(probs):
                lbl = self.label_map.get(idx, "")
                if "entail" in lbl:
                    p_ent += prob
                elif "contradict" in lbl:
                    p_con += prob
                else:
                    p_neu += prob

            if p_ent > max_entail:
                max_entail = p_ent
            if p_con > max_contra:
                max_contra = p_con
            if p_neu < best_neutral:
                best_neutral = p_neu

        # Truth score = max_entailment - max_contradiction
        truth_score = max_entail - max_contra
        return {
            "entailment": float(max_entail),
            "neutral": float(best_neutral),
            "contradiction": float(max_contra),
            "truth_score": float(truth_score),
        }

    def score_batch(self, pairs: Sequence[tuple[str, str]]) -> list[dict[str, float]]:
        """Score a list of (evidence, claim) pairs."""
        return [self.score_pair(ev, cl) for ev, cl in pairs]

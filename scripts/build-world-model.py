#!/usr/bin/env python3
"""
build-world-model.py

Standalone pipeline to build a hybrid BENDER world model from a document corpus.

A hybrid world model contains:
  - a knowledge-graph layer (entities, relations, document structure)
  - a vector layer (embeddings + ANN index for semantic retrieval)

Usage:
  python scripts/build-world-model.py \
      --input path/to/documents.jsonl \
      --output path/to/world_model.json.gz \
      --domain wikipedia \
      --encoder sentence-transformer

Input JSONL format (one document per line):
  {"id": "page_123", "title": "Ada Lovelace", "text": "...", "metadata": {...}}

The pipeline will:
  1. Parse documents into pages / sections.
  2. Extract entities and internal/semantic relations.
  3. Build a BENDER WorldModel graph.
  4. Encode pages/sections into embeddings.
  5. Attach a FaissIndex (or InMemoryGraphIndex) to the world model.
  6. Save the result (WorldModelStore or raw JSON).

No existing files are modified.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import sys

# Ensure src/ is importable when running the script directly.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from octo.retrieval import get_encoder
from octo.retrieval.ann import FaissIndex
from octo.world_model_store import WorldModelStore
from octo.world_state import WorldModel


# ---------------------------------------------------------------------------
# Tokenization / chunking helpers
# ---------------------------------------------------------------------------

WORD_RE = re.compile(r"[a-z0-9_']+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def chunk_text(text: str, chunk_size: int = 256, overlap: int = 32) -> list[str]:
    """Naive sentence-aware chunking."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        sentence_len = len(sentence.split())
        if current_len + sentence_len > chunk_size and current:
            chunks.append(" ".join(current))
            # keep overlap sentences
            overlap_sentences = []
            overlap_len = 0
            for s in reversed(current):
                sl = len(s.split())
                if overlap_len + sl > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_len += sl
            current = overlap_sentences
            current_len = overlap_len
        current.append(sentence)
        current_len += sentence_len
    if current:
        chunks.append(" ".join(current))
    return chunks


# ---------------------------------------------------------------------------
# Entity extraction (lightweight, deterministic)
# ---------------------------------------------------------------------------

WIKI_LINK_RE = re.compile(r"\[\[(?P<title>[^|\]]+)(?:\|(?P<label>[^\]]+))?\]\]")


def extract_wiki_links(text: str) -> list[tuple[str, str]]:
    """Return (target_title, display_label) for all [[...]] links."""
    results: list[tuple[str, str]] = []
    for match in WIKI_LINK_RE.finditer(text):
        title = match.group("title").strip()
        label = (match.group("label") or title).strip()
        results.append((title, label))
    return results


def extract_entities(text: str, title: str) -> list[dict[str, Any]]:
    """Lightweight entity extraction from title-cased phrases and wiki links."""
    entities: list[dict[str, Any]] = []
    seen: set[str] = set()

    # wiki links first
    for target, label in extract_wiki_links(text):
        key = target.lower()
        if key not in seen:
            seen.add(key)
            entities.append({
                "name": target,
                "label": label,
                "type": "wiki_entity",
                "source": "wiki_link",
            })

    # title-cased phrases (simple heuristic)
    for match in re.finditer(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", text):
        name = match.group(1)
        key = name.lower()
        if key not in seen and len(name) > 3:
            seen.add(key)
            entities.append({
                "name": name,
                "label": name,
                "type": "wiki_entity",
                "source": "title_case",
            })

    return entities


# ---------------------------------------------------------------------------
# World model builder
# ---------------------------------------------------------------------------

class HybridWorldModelBuilder:
    """Build a hybrid graph+vector world model from a document corpus."""

    def __init__(
        self,
        *,
        domain: str = "generic",
        encoder_name: str = "all-MiniLM-L6-v2",
        chunk_size: int = 256,
        chunk_overlap: int = 32,
        max_links_per_doc: int = 100,
    ):
        self.domain = domain
        self.encoder_name = encoder_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_links_per_doc = max_links_per_doc
        self.encoder = get_encoder(encoder_name)
        self.use_ann = self.encoder.__class__.__name__ != "HashedTokenEncoder"

    def build(self, documents: Iterable[dict[str, Any]]) -> WorldModel:
        world_model = WorldModel(domain=self.domain, use_ann=self.use_ann)
        documents = list(documents)

        # Pass 1: add document / section / entity nodes and structural edges
        for doc in documents:
            self._add_document(world_model, doc)

        # Pass 2: add cross-document links and semantic relations
        title_to_id = {
            node.get("title", "").lower(): node_id
            for node_id, node in world_model.nodes.items()
            if node.get("type") == "wiki_page"
        }
        for doc in documents:
            self._add_cross_links(world_model, doc, title_to_id)

        # Pass 3: encode and index page/section/chunk nodes
        self._build_vector_index(world_model)

        return world_model

    def _add_document(self, world_model: WorldModel, doc: dict[str, Any]) -> None:
        doc_id = doc["id"]
        title = doc.get("title", doc_id)
        text = doc.get("text", "")
        metadata = doc.get("metadata", {})

        page_node_id = f"page:{doc_id}"
        summary = text[:512] if text else ""
        world_model.upsert_node(
            page_node_id,
            label=title,
            type="wiki_page",
            summary=summary,
            keywords=tokenize(title) + tokenize(summary),
            title=title,
            doc_id=doc_id,
            **metadata,
        )

        # sections / chunks
        chunks = chunk_text(text, self.chunk_size, self.chunk_overlap)
        for idx, chunk_text_value in enumerate(chunks):
            chunk_node_id = f"chunk:{doc_id}:{idx}"
            world_model.upsert_node(
                chunk_node_id,
                label=f"{title} (chunk {idx})",
                type="wiki_chunk",
                summary=chunk_text_value[:400],
                keywords=tokenize(chunk_text_value),
                doc_id=doc_id,
                chunk_index=idx,
            )
            world_model.add_edge(page_node_id, "has_chunk", chunk_node_id, score=0.98)

            # entities within chunk
            for entity in extract_entities(chunk_text_value, title):
                entity_node_id = f"entity:{entity['name'].lower().replace(' ', '_')}"
                world_model.upsert_node(
                    entity_node_id,
                    label=entity["name"],
                    type=entity["type"],
                    summary=f"Entity mentioned in {title}.",
                    keywords=tokenize(entity["name"]),
                )
                world_model.add_edge(chunk_node_id, "mentions", entity_node_id, score=0.85)
                world_model.add_edge(entity_node_id, "mentioned_in", page_node_id, score=0.80)

    def _add_cross_links(
        self,
        world_model: WorldModel,
        doc: dict[str, Any],
        title_to_id: dict[str, str],
    ) -> None:
        doc_id = doc["id"]
        text = doc.get("text", "")
        page_node_id = f"page:{doc_id}"

        links = extract_wiki_links(text)[: self.max_links_per_doc]
        for target, _ in links:
            target_lower = target.lower()
            target_node_id = title_to_id.get(target_lower)
            if target_node_id and target_node_id != page_node_id:
                world_model.add_edge(page_node_id, "links_to", target_node_id, score=0.95)

    def _build_vector_index(self, world_model: WorldModel) -> None:
        node_ids = []
        texts = []
        metadata = []
        for node_id, node in world_model.nodes.items():
            if node.get("type") not in ("wiki_page", "wiki_chunk"):
                continue
            text = world_model.embedding_text(node_id)
            if not text:
                continue
            node_ids.append(node_id)
            texts.append(text)
            metadata.append(dict(node))

        if not node_ids:
            return

        embeddings = self.encoder.encode(texts)
        if self.use_ann:
            ann_index = FaissIndex(self.encoder.dimension)
            ann_index.add_records(node_ids, texts, embeddings, metadata)
            world_model._ann_index = ann_index
            world_model._encoder = self.encoder

        # also attach an in-memory graph index as fallback
        from octo.retrieval import InMemoryGraphIndex

        records = [(node_id, texts[i], metadata[i]) for i, node_id in enumerate(node_ids)]
        world_model._index = InMemoryGraphIndex.from_records(records)

        world_model._dirty = False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_documents(path: str) -> Iterable[dict[str, Any]]:
    p = Path(path)
    if p.suffix == ".jsonl" or p.suffix == ".gz":
        opener = gzip.open if str(p).endswith(".gz") else open
        with opener(p, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)
    elif p.suffix == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            yield from data
        else:
            yield data
    else:
        raise ValueError(f"Unsupported input format: {p.suffix}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a hybrid BENDER world model.")
    parser.add_argument("--input", required=True, help="Path to input documents (.jsonl, .json, or .jsonl.gz).")
    parser.add_argument("--output", required=True, help="Output path for world model (.json, .json.gz, or directory for WorldModelStore).")
    parser.add_argument("--domain", default="generic", help="Domain tag for the world model.")
    parser.add_argument("--encoder", default="all-MiniLM-L6-v2", help="Sentence-transformer model name.")
    parser.add_argument("--chunk-size", type=int, default=256, help="Chunk size in tokens/words.")
    parser.add_argument("--chunk-overlap", type=int, default=32, help="Overlap between chunks.")
    parser.add_argument("--store", action="store_true", help="Use WorldModelStore versioning instead of raw JSON.")
    parser.add_argument("--source", default="generic", help="Source identifier for WorldModelStore.")
    parser.add_argument("--version", default="v1.0.0", help="Version for WorldModelStore.")
    parser.add_argument("--model-id", default="default", help="Model ID for WorldModelStore.")
    args = parser.parse_args()

    print(f"Loading documents from {args.input}...")
    documents = list(load_documents(args.input))
    print(f"Loaded {len(documents)} documents.")

    print("Building hybrid world model...")
    builder = HybridWorldModelBuilder(
        domain=args.domain,
        encoder_name=args.encoder,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    world_model = builder.build(documents)

    print(f"World model: {len(world_model.nodes)} nodes, {len(world_model.edges)} edges.")

    if args.store:
        store = WorldModelStore(args.output)
        store.save(world_model, source=args.source, version=args.version, model_id=args.model_id)
        print(f"Saved to WorldModelStore: {args.output}/{args.source}/{args.version}/{args.model_id}")
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if str(output_path).endswith(".gz"):
            with gzip.open(output_path, "wt", encoding="utf-8") as f:
                f.write(json.dumps(world_model.to_dict(), indent=2))
        else:
            output_path.write_text(json.dumps(world_model.to_dict(), indent=2), encoding="utf-8")
        print(f"Saved world model to {output_path}")


if __name__ == "__main__":
    main()

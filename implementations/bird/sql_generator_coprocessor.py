"""
SQL generator as a first-class OCTO coprocessor.

Each SQL generator is a domain-specialized coprocessor that consumes a
`BirdExecutionPacket` (grounded schema + question + evidence) and emits a list
of `BirdSQLCandidate` objects. Multiple generators can be composed into an
ensemble, sequenced with fallbacks, or selected per-task.

This makes the generation step look like the rest of the OCTO architecture:
a runtime loop that delegates to specialized, swappable coprocessors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .bird import (
    BirdExecutionPacket,
    BirdHeuristicSQLCandidateGenerator,
    BirdOllamaSQLCandidateGenerator,
    BirdSQLCandidate,
)
from .claude_generator import BirdClaudeSQLCandidateGenerator


class SQLGeneratorCoprocessor(ABC):
    """Abstract base for a SQL-generation coprocessor.

    A SQL generator coprocessor is a specialized agent that turns a grounded
    execution packet into ranked SQL candidates. It is intentionally small and
    stateless so that several can be composed into an ensemble.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in provenance and strategy metadata."""
        ...

    @abstractmethod
    def generate(
        self, packet: BirdExecutionPacket, *, max_candidates: int = 4
    ) -> list[BirdSQLCandidate]:
        """Generate SQL candidates from the grounded packet.

        Args:
            packet: Grounded question + schema + candidate tables.
            max_candidates: Maximum candidates this coprocessor should return.

        Returns:
            A list of SQL candidates (possibly empty).
        """
        ...

    def run(
        self, packet: BirdExecutionPacket, *, max_candidates: int = 4
    ) -> list[BirdSQLCandidate]:
        """Convenience alias for `generate` matching other coprocessor APIs."""
        return self.generate(packet, max_candidates=max_candidates)


@dataclass
class HeuristicSQLGeneratorCoprocessor(SQLGeneratorCoprocessor):
    """Coprocessor wrapper around the heuristic SQL generator."""

    generator: BirdHeuristicSQLCandidateGenerator = field(
        default_factory=BirdHeuristicSQLCandidateGenerator
    )

    @property
    def name(self) -> str:
        return "heuristic"

    def generate(
        self, packet: BirdExecutionPacket, *, max_candidates: int = 4
    ) -> list[BirdSQLCandidate]:
        candidates = self.generator.generate(packet, max_candidates=max_candidates)
        for candidate in candidates:
            candidate.metadata = {**(candidate.metadata or {}), "coprocessor": self.name}
        return candidates


@dataclass
class OllamaSQLGeneratorCoprocessor(SQLGeneratorCoprocessor):
    """Coprocessor wrapper around the Ollama SQL generator."""

    generator: BirdOllamaSQLCandidateGenerator | None = None
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5-coder:latest"
    strict: bool = False
    temperatures: tuple[float, ...] = (0.0, 0.1, 0.2)

    def __post_init__(self) -> None:
        if self.generator is None:
            self.generator = BirdOllamaSQLCandidateGenerator(
                base_url=self.base_url,
                model=self.model,
                strict=self.strict,
                temperatures=self.temperatures,
            )

    @property
    def name(self) -> str:
        return f"ollama:{self.generator.model}"

    def generate(
        self, packet: BirdExecutionPacket, *, max_candidates: int = 4
    ) -> list[BirdSQLCandidate]:
        candidates = self.generator.generate(packet, max_candidates=max_candidates)
        for candidate in candidates:
            candidate.metadata = {**(candidate.metadata or {}), "coprocessor": self.name}
        return candidates


@dataclass
class ClaudeSQLGeneratorCoprocessor(SQLGeneratorCoprocessor):
    """Coprocessor wrapper around the Claude SQL generator."""

    generator: BirdClaudeSQLCandidateGenerator | None = None
    api_key: str | None = None
    model: str = "claude-3-5-sonnet-20241022"  # widely available Claude model
    max_tokens: int = 2048
    temperatures: tuple[float, ...] = (0.0, 0.3, 0.7)
    strict: bool = False

    def __post_init__(self) -> None:
        if self.generator is None:
            self.generator = BirdClaudeSQLCandidateGenerator(
                api_key=self.api_key,
                model=self.model,
                max_tokens=self.max_tokens,
                temperatures=self.temperatures,
                strict=self.strict,
            )

    @property
    def name(self) -> str:
        return f"claude:{self.generator.model}"

    def generate(
        self, packet: BirdExecutionPacket, *, max_candidates: int = 4
    ) -> list[BirdSQLCandidate]:
        candidates = self.generator.generate(packet, max_candidates=max_candidates)
        for candidate in candidates:
            candidate.metadata = {**(candidate.metadata or {}), "coprocessor": self.name}
        return candidates


@dataclass
class FallbackSQLGeneratorCoprocessor(SQLGeneratorCoprocessor):
    """Run a primary coprocessor, then a fallback if the primary returns nothing.

    This models the common pattern: "try the LLM, but always have a heuristic
    safety net."
    """

    primary: SQLGeneratorCoprocessor
    fallback: SQLGeneratorCoprocessor

    @property
    def name(self) -> str:
        return f"fallback({self.primary.name},{self.fallback.name})"

    def generate(
        self, packet: BirdExecutionPacket, *, max_candidates: int = 4
    ) -> list[BirdSQLCandidate]:
        candidates = self.primary.generate(packet, max_candidates=max_candidates)
        if not candidates:
            candidates = self.fallback.generate(packet, max_candidates=max_candidates)
        return candidates


@dataclass
class EnsembleSQLGeneratorCoprocessor(SQLGeneratorCoprocessor):
    """Aggregate candidates from multiple SQL generator coprocessors.

    The ensemble runs every child coprocessor, deduplicates by SQL text,
    preserves provenance (which coprocessor produced each candidate), and
    returns up to `max_candidates` unique SQL statements.

    This is the concrete realization of "multiple world coprocessors acting
    together in the generation step."
    """

    coprocessors: list[SQLGeneratorCoprocessor]

    @property
    def name(self) -> str:
        return f"ensemble({','.join(c.name for c in self.coprocessors)})"

    def generate(
        self, packet: BirdExecutionPacket, *, max_candidates: int = 4
    ) -> list[BirdSQLCandidate]:
        all_candidates: list[BirdSQLCandidate] = []
        for coprocessor in self.coprocessors:
            candidates = coprocessor.generate(packet, max_candidates=max_candidates)
            for candidate in candidates:
                candidate.metadata = {
                    **(candidate.metadata or {}),
                    "coprocessor": coprocessor.name,
                }
            all_candidates.extend(candidates)

        deduped: list[BirdSQLCandidate] = []
        seen: set[str] = set()
        for candidate in all_candidates:
            sql = candidate.sql.strip()
            if not sql or sql in seen:
                continue
            seen.add(sql)
            deduped.append(candidate)

        return deduped[:max_candidates]


@dataclass
class TrainedSQLGeneratorCoprocessor(SQLGeneratorCoprocessor):
    """Coprocessor wrapper around a locally trained HuggingFace SQL generator.

    This is the integration point for models trained on the DGX (or elsewhere).
    The model consumes the same grounded packet as Claude/Ollama/heuristic
    generators and emits SQL candidates.
    """

    model_path: str
    device: str = "auto"
    max_new_tokens: int = 512
    temperature: float = 0.0
    do_sample: bool = False
    _tokenizer: Any = field(default=None, repr=False)
    _model: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "transformers package required for TrainedSQLGeneratorCoprocessor"
            ) from exc

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_path, trust_remote_code=True
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype="auto",
            device_map=self.device,
            trust_remote_code=True,
        )

    @property
    def name(self) -> str:
        return f"trained:{Path(self.model_path).name}"

    def _format_prompt(self, packet: BirdExecutionPacket) -> str:
        allowed = {table.name.lower() for table in packet.snapshot.tables}
        if packet.candidate_tables:
            allowed = {name.lower() for name in packet.candidate_tables}

        table_blocks: list[str] = []
        for table in packet.snapshot.tables:
            if table.name.lower() not in allowed:
                continue
            columns = ", ".join(
                f"{column.name} {column.data_type}" for column in table.columns
            )
            table_blocks.append(f"TABLE {table.name} ({columns})")
        schema_text = "\n".join(table_blocks) if table_blocks else "(no filtered tables)"

        evidence_text = ""
        if packet.include_evidence and packet.evidence.strip():
            evidence_text = f"\nEvidence: {packet.evidence.strip()}"

        instruction = (
            "You are writing SQLite SQL for the BIRD benchmark.\n"
            "Return only SQL.\n"
            "Use only the tables shown below when possible.\n"
        )
        input_text = (
            f"Database: {packet.db_id}\n"
            f"Schema:\n{schema_text}\n\n"
            f"Question: {packet.question}{evidence_text}"
        )
        return (
            f"{instruction}\n\n### Input:\n{input_text}\n\n### Response:\n"
        )

    def generate(
        self, packet: BirdExecutionPacket, *, max_candidates: int = 4
    ) -> list[BirdSQLCandidate]:
        if self._model is None or self._tokenizer is None:
            raise RuntimeError("Model not loaded")

        prompt = self._format_prompt(packet)
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)

        outputs = self._model.generate(
            **inputs,
            max_new_tokens=self.max_new_tokens,
            temperature=self.temperature if self.do_sample else None,
            do_sample=self.do_sample,
            pad_token_id=self._tokenizer.pad_token_id,
            eos_token_id=self._tokenizer.eos_token_id,
        )

        generated_text = self._tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )
        from .bird import _extract_sql

        sql = _extract_sql(generated_text)
        if not sql:
            return []

        candidate = BirdSQLCandidate(
            sql=sql,
            strategy=self.name,
            rationale=f"Generated by local trained model {self.name}",
            metadata={"coprocessor": self.name, "model_path": self.model_path},
        )
        return [candidate]


def as_coprocessor(
    generator: Any,
) -> SQLGeneratorCoprocessor:
    """Lift a legacy `BirdSQLCandidateGenerator` into the coprocessor interface.

    This keeps existing callers working while the codebase migrates to the
    coprocessor model.
    """
    if isinstance(generator, SQLGeneratorCoprocessor):
        return generator
    if isinstance(generator, BirdHeuristicSQLCandidateGenerator):
        return HeuristicSQLGeneratorCoprocessor(generator=generator)
    if isinstance(generator, BirdOllamaSQLCandidateGenerator):
        return OllamaSQLGeneratorCoprocessor(generator=generator)
    if isinstance(generator, BirdClaudeSQLCandidateGenerator):
        return ClaudeSQLGeneratorCoprocessor(generator=generator)
    raise TypeError(f"Cannot wrap {type(generator).__name__} as SQLGeneratorCoprocessor")

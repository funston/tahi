"""
Claude SQL Generator Coprocessor for BIRD

Uses Anthropic Claude API for high-quality SQL generation.
This is a BLACK-BOX integration - Claude doesn't support native coprocessor mode.
OCTO provides structured grounding context in the prompt.

Works with any Anthropic model, including:
- claude-opus-4-20250514 (most capable, most expensive)
- claude-sonnet-4-20250514 (strong, cheaper)
- claude-haiku-... (fastest, weakest)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .bird import (
    BirdExecutionPacket,
    BirdSQLCandidate,
    _extract_sql,
)


@dataclass
class BirdClaudeSQLCandidateGenerator:
    """
    SQL generator using Anthropic Claude API.

    This is a black-box integration - OCTO grounding context
    is provided in the system prompt, not as native coprocessor signal.
    """

    api_key: str | None = None
    model: str = "claude-3-5-sonnet-20241022"  # widely available Claude model
    max_tokens: int = 2048
    temperatures: tuple[float, ...] = (0.0, 0.3, 0.7)
    strict: bool = False

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable must be set or api_key provided"
            )

        # Import here to avoid requiring anthropic for other generators
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError as e:
            raise ImportError(
                "anthropic package required. Install with: pip install anthropic"
            ) from e

    def generate(
        self,
        packet: BirdExecutionPacket,
        *,
        max_candidates: int = 3,
    ) -> list[BirdSQLCandidate]:
        """
        Generate SQL candidates using Claude 3.5 Sonnet.

        Args:
            packet: BIRD execution packet with question, schema, candidate_tables
            max_candidates: Number of SQL candidates to generate

        Returns:
            List of BirdSQLCandidate with generated SQL
        """
        candidates: list[BirdSQLCandidate] = []
        errors: list[str] = []

        # Build system prompt with OCTO grounding context
        system_prompt = self._build_system_prompt(packet)

        # Build user message
        user_message = self._build_user_message(packet)

        # Generate candidates with different temperatures
        for i in range(max_candidates):
            temperature = self.temperatures[i % len(self.temperatures)]

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": user_message,
                        }
                    ],
                )

                # Extract SQL from Claude response
                response_text = response.content[0].text
                sql = _extract_sql(response_text)

                if not sql:
                    continue

                candidates.append(
                    BirdSQLCandidate(
                        sql=sql,
                        strategy=self.model,
                        rationale=f"Claude {self.model} with OCTO grounding (temp={temperature})",
                        metadata={
                            "temperature": temperature,
                            "model": self.model,
                            "stop_reason": response.stop_reason,
                        },
                    )
                )

            except Exception as exc:  # noqa: BLE001
                error_msg = f"Candidate {i}: {type(exc).__name__}: {exc}"
                errors.append(error_msg)
                import sys
                print(f"[CLAUDE ERROR] {error_msg}", file=sys.stderr)

        # Dedup candidates
        deduped: list[BirdSQLCandidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            sql = candidate.sql.strip()
            if not sql or sql in seen:
                continue
            seen.add(sql)
            deduped.append(candidate)

        if deduped:
            return deduped[:max_candidates]

        if self.strict:
            detail = "; ".join(errors) if errors else "empty_candidate_set"
            raise RuntimeError(f"Claude SQL generation failed: {detail}")

        return []

    def _build_system_prompt(self, packet: BirdExecutionPacket) -> str:
        """
        Build system prompt with OCTO grounding context.

        This is where OCTO's value shows up in black-box mode:
        - Filtered schema (candidate_tables from world model)
        - Structural constraints from coprocessor
        """
        # Build filtered schema with actual column names and types
        schema_blocks: list[str] = []
        candidate_set = set(packet.candidate_tables) if packet.candidate_tables else set()

        for table in packet.snapshot.tables:
            if candidate_set and table.name not in candidate_set:
                continue

            # Format as CREATE TABLE for clarity
            columns_with_types = [
                f"    {column.name} {column.data_type}"
                for column in table.columns
            ]
            schema_block = f"CREATE TABLE {table.name} (\n" + ",\n".join(columns_with_types) + "\n);"
            schema_blocks.append(schema_block)

        schema_text = "\n\n".join(schema_blocks) if schema_blocks else "(no tables)"

        # OCTO grounding context
        grounding_note = ""
        if packet.candidate_tables:
            grounding_note = (
                f"\n\nOCTO World Model Analysis:\n"
                f"- Relevant tables identified: {', '.join(packet.candidate_tables)}\n"
                f"- These tables were selected by the coprocessor based on semantic relevance to the question"
            )

        return f"""You are an expert SQL query generator for the BIRD text-to-SQL benchmark.

Database: {packet.db_id}

Schema (filtered by OCTO coprocessor to relevant tables):
{schema_text}{grounding_note}

IMPORTANT REQUIREMENTS:
1. Generate SQLite-compatible SQL only
2. Use ONLY the tables and columns shown in the schema above
3. Return valid, executable SQL with proper syntax
4. Place SQL in a ```sql code block
5. Do not hallucinate column names - use exact names from schema
6. Ensure all parentheses are balanced and queries are complete"""

    def _build_user_message(self, packet: BirdExecutionPacket) -> str:
        """Build user message with question and evidence."""
        message = f"Question: {packet.question}"

        if packet.include_evidence and packet.evidence.strip():
            message += f"\n\nEvidence/Hint: {packet.evidence.strip()}"

        message += "\n\nGenerate a SQL query to answer this question. Return only the SQL in a ```sql block."

        return message

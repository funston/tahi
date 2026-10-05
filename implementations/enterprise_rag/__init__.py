"""EnterpriseRAG-Bench adapter for TAHI evaluation."""

from .dataset import (
    CATEGORY_COUNTS,
    STRUCTURE_SENSITIVE,
    EnterpriseDocument,
    EnterpriseQuestion,
    iter_documents,
    load_questions,
    summarize,
)

__all__ = [
    "CATEGORY_COUNTS",
    "STRUCTURE_SENSITIVE",
    "EnterpriseDocument",
    "EnterpriseQuestion",
    "iter_documents",
    "load_questions",
    "summarize",
]

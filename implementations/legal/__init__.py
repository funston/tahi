"""OCTO legal world coprocessor and LegalBench evaluation."""

from .legal_coprocessor import LegalWorldCoprocessor, LegalQuestion
from .legalbench_eval import build_default_coprocessor, load_legalbench_sample, evaluate_legal_coprocessor

__all__ = [
    "LegalWorldCoprocessor",
    "LegalQuestion",
    "build_default_coprocessor",
    "load_legalbench_sample",
    "evaluate_legal_coprocessor",
]

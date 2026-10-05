"""Shared pytest configuration for the TAHI test suite."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

if SRC not in sys.path:
 sys.path.insert(0, SRC)
if ROOT not in sys.path:
 sys.path.insert(0, ROOT)

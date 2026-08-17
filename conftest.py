"""
conftest.py — Pytest configuration for the Monte Carlo SQL Validator.

Adds the project root to sys.path so that ``src.*`` imports resolve
correctly when running tests from any working directory.
"""

import sys
from pathlib import Path

# Ensure project root is on the path for both pytest and Pylance
sys.path.insert(0, str(Path(__file__).resolve().parent))

"""Eval harness for agent-core (M4.3 / M4.4).

Entry points::

    python -m eval.run --profile local
    python -m eval.run --profile gemini
    python -m eval.compare

``GOLDEN_SET_PATH`` points at the YAML file that defines the 15 golden cases
(docs/agent-core/08-eval-harness.md §2).
"""
from __future__ import annotations

from pathlib import Path

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.yaml"
RESULTS_DIR = Path(__file__).parent / "results"

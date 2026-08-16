"""Tests for eval/compare.py delta columns and formatting."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

from eval.compare import _print_comparison, _score_str


def test_score_str_formatting():
    assert _score_str({"playbook": True, "tools": True, "no_hallucination": True, "policy": True, "verification": True}) == "5/5"
    assert _score_str({"playbook": True, "tools": False, "no_hallucination": True, "policy": True, "verification": True}) == "4/5 (tool)"
    assert _score_str({"playbook": False, "tools": True, "no_hallucination": True, "policy": False, "verification": True}) == "3/5 (play, policy)"


def test_comparison_table_contains_delta_and_simulated_tag():
    local_data = {
        "profile": "local",
        "timestamp": "20260816T120000",
        "total_score": 0.8,
        "avg_latency_ms": 200,
        "cases": [
            {
                "case_id": "G01",
                "scenario": "Test G01",
                "scores": {"playbook": True, "tools": True, "no_hallucination": True, "policy": True, "verification": True},
                "score": 1.0,
                "latency_ms": 200,
                "schema_retries": 0,
                "skipped": False,
            }
        ],
    }

    gemini_data = {
        "profile": "gemini",
        "timestamp": "20260816T120500",
        "total_score": 1.0,
        "avg_latency_ms": 150,
        "cases": [
            {
                "case_id": "G01",
                "scenario": "Test G01",
                "scores": {"playbook": True, "tools": True, "no_hallucination": True, "policy": True, "verification": True},
                "score": 1.0,
                "latency_ms": 150,
                "schema_retries": 0,
                "skipped": False,
            }
        ],
    }

    buf = io.StringIO()
    with redirect_stdout(buf):
        _print_comparison(local_data, gemini_data)

    out = buf.getvalue()
    assert "Δ Score" in out
    assert "Δ Latency" in out
    assert "SIMULATED" in out
    assert "| G01 | 5/5 | 5/5 | +0 | 200ms | 150ms | -50ms |" in out


def test_comparison_empty_data_does_not_crash():
    buf = io.StringIO()
    with redirect_stdout(buf):
        _print_comparison(None, None)
    out = buf.getvalue()
    assert "No results found" in out

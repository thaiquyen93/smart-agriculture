"""Tests for eval/run.py CLI execution and summary printing."""
from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from eval.run import _print_summary, main
from eval.runner import CaseResult, RunResult


def test_print_summary_does_not_crash_on_case_id():
    cases = [
        CaseResult("G01", "Scenario 1", [True] * 5, 1.0, 120, 0),
        CaseResult("G02", "Scenario 2", [True, False, True, True, True], 0.8, 150, 0, skipped=True, skip_reason="manual skip"),
    ]
    rr = RunResult(profile="local", timestamp="20260816T120000", cases=cases)

    buf = io.StringIO()
    with redirect_stdout(buf):
        _print_summary(rr)

    output = buf.getvalue()
    assert "G01" in output
    assert "G02" in output
    assert "SKIP — manual skip" in output


def test_run_cli_smoke_all_cases():
    exit_code = main(["--profile", "local", "--no-save"])
    assert exit_code == 0


def test_run_cli_smoke_specific_cases():
    exit_code = main(["--profile", "gemini", "--case", "G01", "G06", "--no-save"])
    assert exit_code == 0

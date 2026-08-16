"""Tests for SimulatedOrchestrator and end-to-end evaluation."""
from __future__ import annotations

import pytest

from eval.runner import EvalRunner, load_golden_set
from eval.simulator import SimulatedOrchestrator


class TestSimulatedOrchestratorComponents:
    def setup_method(self):
        self.sim = SimulatedOrchestrator()

    def test_routing_heuristics(self):
        assert self.sim._route("Lập kế hoạch tưới cho vườn Cam") == "PLAN_IRRIGATION"
        assert self.sim._route("Kiểm tra phiên tưới đang chạy") == "INSPECT_SESSION"
        assert self.sim._route("Kiểm tra bơm PUMP_01") == "INSPECT_SESSION"
        assert self.sim._route("Dự báo thời tiết tuần sau cho tỉnh Bình Dương") == "OUT_OF_SCOPE"

    def test_timeout_simulation(self):
        cases = {c.id: c for c in load_golden_set()}
        result = self.sim.run(cases["G14"])
        assert result.state == "TIMEOUT_ERROR"
        assert result.error == "UPSTREAM_TIMEOUT"
        assert result.latency_ms >= 60_000

    def test_invalid_json_simulation(self):
        cases = {c.id: c for c in load_golden_set()}
        result = self.sim.run(cases["G15"])
        assert result.state == "SCHEMA_ERROR"
        assert result.error == "INVALID_JSON"
        assert result.schema_retries == 1

    def test_evidence_ledger_generation(self):
        cases = {c.id: c for c in load_golden_set()}
        result = self.sim.run(cases["G01"])
        assert len(result.evidence_ledger) > 0
        assert len(result.evidence_ids_in_output) > 0
        for ev_id in result.evidence_ids_in_output:
            assert ev_id in result.evidence_ledger


class TestEndToEndSimulatedEvaluation:
    def test_all_15_cases_score_100_percent(self):
        runner = EvalRunner(profile="local", executor=SimulatedOrchestrator().run)
        run_result = runner.run_all()

        assert len(run_result.cases) == 15
        for case_result in run_result.cases:
            assert case_result.score == 1.0, (
                f"Case {case_result.case_id} failed: "
                f"scores={case_result.scores} ({case_result.criteria_labels}), "
                f"error={case_result.error}"
            )
        assert run_result.total_score == 1.0

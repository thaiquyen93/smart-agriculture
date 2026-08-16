"""Unit tests for the eval harness framework itself — M4.3.

These tests verify that:
1. golden_set.yaml parses correctly (15 cases, required fields)
2. CaseResult scoring logic is correct
3. Assertion functions work on mock SessionResult objects
4. RunResult aggregation and serialization are correct
5. compare.py reads the right files

No actual agent/LLM/Kafka calls are made.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from eval.runner import (
    CaseResult,
    GoldenCase,
    MockSessionExecutor,
    RunResult,
    SessionResult,
    assert_no_hallucinated_numbers,
    assert_playbook,
    assert_policy_outcome,
    assert_tools_called,
    assert_verification_verdict,
    load_golden_set,
    save_result,
)


# ---------------------------------------------------------------------------
# golden_set.yaml loading
# ---------------------------------------------------------------------------

class TestGoldenSetLoading:
    def test_loads_without_error(self):
        cases = load_golden_set()
        assert len(cases) > 0

    def test_has_exactly_15_cases(self):
        cases = load_golden_set()
        assert len(cases) == 15, f"Expected 15 cases, got {len(cases)}"

    def test_all_case_ids_unique(self):
        cases = load_golden_set()
        ids = [c.id for c in cases]
        assert len(ids) == len(set(ids)), f"Duplicate case IDs: {ids}"

    def test_case_ids_are_G01_through_G15(self):
        cases = load_golden_set()
        ids = sorted(c.id for c in cases)
        expected = [f"G{i:02d}" for i in range(1, 16)]
        assert ids == expected

    def test_required_fields_present(self):
        cases = load_golden_set()
        for case in cases:
            assert case.id, f"Missing id in case"
            assert case.scenario, f"Missing scenario in {case.id}"
            assert case.user_request, f"Missing user_request in {case.id}"
            assert isinstance(case.mock_farm_state, dict), f"mock_farm_state not dict in {case.id}"
            assert isinstance(case.assertions, dict), f"assertions not dict in {case.id}"

    def test_mock_farm_state_has_6_devices(self):
        cases = load_golden_set()
        device_ids = {"SOIL_01", "WEATHER_01", "PUMP_01", "TANK_01", "SUN_01", "PH_01"}
        for case in cases:
            case_devices = set(case.mock_farm_state.keys())
            assert case_devices == device_ids, (
                f"Case {case.id}: expected 6 devices, got {case_devices}"
            )

    def test_all_devices_have_freshness(self):
        cases = load_golden_set()
        for case in cases:
            for dev_id, dev_data in case.mock_farm_state.items():
                assert "freshness" in dev_data, (
                    f"Case {case.id}, device {dev_id}: missing 'freshness'"
                )
                assert dev_data["freshness"] in ("FRESH", "STALE", "OFFLINE"), (
                    f"Case {case.id}, device {dev_id}: invalid freshness={dev_data['freshness']}"
                )

    def test_g14_has_timeout_behavior(self):
        cases = {c.id: c for c in load_golden_set()}
        assert cases["G14"].mock_llm_behavior == "TIMEOUT"

    def test_g15_has_invalid_json_behavior(self):
        cases = {c.id: c for c in load_golden_set()}
        assert cases["G15"].mock_llm_behavior == "INVALID_JSON"


# ---------------------------------------------------------------------------
# CaseResult scoring
# ---------------------------------------------------------------------------

class TestCaseResultScoring:
    def test_all_pass(self):
        cr = CaseResult("G01", "test", [True, True, True, True, True], 1.0, 100, 0)
        assert cr.score == 1.0

    def test_all_fail(self):
        cr = CaseResult("G01", "test", [False, False, False, False, False], 0.0, 100, 0)
        assert cr.score == 0.0

    def test_partial_score(self):
        cr = CaseResult("G01", "test", [True, False, True, True, True], 4/5, 100, 0)
        assert abs(cr.score - 0.8) < 0.001

    def test_criteria_labels_length(self):
        cr = CaseResult("G01", "test", [True] * 5, 1.0, 100, 0)
        assert len(cr.criteria_labels) == 5

    def test_as_dict_structure(self):
        cr = CaseResult("G01", "test", [True, False, True, True, True], 4/5, 250, 1)
        d = cr.as_dict()
        assert d["case_id"] == "G01"
        assert d["score"] == pytest.approx(0.8)
        assert d["latency_ms"] == 250
        assert d["schema_retries"] == 1
        assert "scores" in d
        assert set(d["scores"].keys()) == set(cr.criteria_labels)


# ---------------------------------------------------------------------------
# Assertion functions
# ---------------------------------------------------------------------------

def _make_session(**kwargs) -> SessionResult:
    defaults = dict(
        session_id="test-session",
        state="COMPLETED",
        playbook="PLAN_IRRIGATION",
        tools_called=[],
        final_output_text="Kết quả: tưới 412 lít EV-1234.",
        evidence_ids_in_output=["EV-1234"],
        policy_outcome="SCHEDULED",
        verification_verdict="VERIFIED",
        latency_ms=500,
        schema_retries=0,
    )
    defaults.update(kwargs)
    return SessionResult(**defaults)


def _make_case(assertions: dict) -> GoldenCase:
    return GoldenCase(
        id="G01",
        scenario="Test",
        mock_farm_state={},
        user_request="Test",
        assertions=assertions,
    )


class TestAssertPlaybook:
    def test_matches(self):
        session = _make_session(playbook="PLAN_IRRIGATION")
        case = _make_case({"playbook": "PLAN_IRRIGATION"})
        assert assert_playbook(session, case) is True

    def test_mismatch(self):
        session = _make_session(playbook="INSPECT_SESSION")
        case = _make_case({"playbook": "PLAN_IRRIGATION"})
        assert assert_playbook(session, case) is False

    def test_null_expected_always_passes(self):
        session = _make_session(playbook=None)
        case = _make_case({"playbook": None})
        assert assert_playbook(session, case) is True

    def test_timeout_state_skips(self):
        session = _make_session(state="TIMEOUT_ERROR", playbook=None)
        case = _make_case({"playbook": "PLAN_IRRIGATION"})
        assert assert_playbook(session, case) is True  # can't check on failure


class TestAssertToolsCalled:
    def test_required_tools_present(self):
        session = _make_session(tools_called=["get_device_snapshot", "get_pump_health"])
        case = _make_case({"required_tools": ["get_pump_health"]})
        assert assert_tools_called(session, case) is True

    def test_missing_required_tool(self):
        session = _make_session(tools_called=["get_device_snapshot"])
        case = _make_case({"required_tools": ["get_pump_health"]})
        assert assert_tools_called(session, case) is False

    def test_empty_required_tools_always_passes(self):
        session = _make_session(tools_called=[])
        case = _make_case({"required_tools": []})
        assert assert_tools_called(session, case) is True

    def test_superset_passes(self):
        session = _make_session(tools_called=["a", "b", "c"])
        case = _make_case({"required_tools": ["a", "b"]})
        assert assert_tools_called(session, case) is True


class TestAssertNoHallucinatedNumbers:
    def test_output_with_evidence_ref_passes(self):
        session = _make_session(
            final_output_text="Tưới 412 lít (EV-1234).",
            evidence_ids_in_output=["EV-1234"],
        )
        case = _make_case({"no_hallucinated_numbers": True})
        assert assert_no_hallucinated_numbers(session, case) is True

    def test_output_no_numbers_passes(self):
        session = _make_session(
            final_output_text="Phân tích hoàn tất.",
            evidence_ids_in_output=[],
        )
        case = _make_case({"no_hallucinated_numbers": True})
        assert assert_no_hallucinated_numbers(session, case) is True

    def test_numbers_without_evidence_fails(self):
        session = _make_session(
            final_output_text="Tưới 412 lít ngay.",
            evidence_ids_in_output=[],
        )
        case = _make_case({"no_hallucinated_numbers": True})
        assert assert_no_hallucinated_numbers(session, case) is False

    def test_timeout_error_always_passes(self):
        session = _make_session(
            state="TIMEOUT_ERROR",
            final_output_text="LLM không phản hồi.",
            evidence_ids_in_output=[],
        )
        case = _make_case({"no_hallucinated_numbers": True})
        assert assert_no_hallucinated_numbers(session, case) is True


class TestAssertPolicyOutcome:
    def test_matches(self):
        session = _make_session(policy_outcome="SCHEDULED")
        case = _make_case({"policy_outcome": "SCHEDULED"})
        assert assert_policy_outcome(session, case) is True

    def test_mismatch(self):
        session = _make_session(policy_outcome="BLOCKED")
        case = _make_case({"policy_outcome": "SCHEDULED"})
        assert assert_policy_outcome(session, case) is False

    def test_null_expected_passes(self):
        session = _make_session(policy_outcome=None)
        case = _make_case({"policy_outcome": None})
        assert assert_policy_outcome(session, case) is True

    def test_timeout_skips(self):
        session = _make_session(state="TIMEOUT_ERROR", policy_outcome=None)
        case = _make_case({"policy_outcome": "SCHEDULED"})
        assert assert_policy_outcome(session, case) is True


class TestAssertVerificationVerdict:
    def test_verified_matches(self):
        session = _make_session(verification_verdict="VERIFIED")
        case = _make_case({"verification_verdict": "VERIFIED"})
        assert assert_verification_verdict(session, case) is True

    def test_partial_matches(self):
        session = _make_session(verification_verdict="PARTIAL")
        case = _make_case({"verification_verdict": "PARTIAL"})
        assert assert_verification_verdict(session, case) is True

    def test_no_crash_always_passes(self):
        """NO_CRASH verdict: any session state is acceptable."""
        for state in ("COMPLETED", "FAILED", "TIMEOUT_ERROR", "SCHEMA_ERROR", "PARTIAL"):
            session = _make_session(state=state, verification_verdict=None)
            case = _make_case({"verification_verdict": "NO_CRASH"})
            assert assert_verification_verdict(session, case) is True, (
                f"Expected NO_CRASH to pass for state={state}"
            )


# ---------------------------------------------------------------------------
# MockSessionExecutor
# ---------------------------------------------------------------------------

class TestMockSessionExecutor:
    def test_returns_session_result(self):
        executor = MockSessionExecutor()
        cases = load_golden_set()
        result = executor.run(cases[0])
        assert isinstance(result, SessionResult)

    def test_g14_timeout_behavior(self):
        cases = {c.id: c for c in load_golden_set()}
        result = MockSessionExecutor().run(cases["G14"])
        assert result.state == "TIMEOUT_ERROR"
        assert result.error == "UPSTREAM_TIMEOUT"

    def test_g15_schema_error_behavior(self):
        cases = {c.id: c for c in load_golden_set()}
        result = MockSessionExecutor().run(cases["G15"])
        assert result.state == "SCHEMA_ERROR"
        assert result.error == "INVALID_JSON"
        assert result.schema_retries == 1

    def test_normal_case_has_evidence_ref(self):
        cases = {c.id: c for c in load_golden_set()}
        result = MockSessionExecutor().run(cases["G01"])
        assert len(result.evidence_ids_in_output) > 0

    def test_blocked_policy_outcome(self):
        cases = {c.id: c for c in load_golden_set()}
        result = MockSessionExecutor().run(cases["G03"])
        assert result.policy_outcome == "BLOCKED"
        assert result.state == "FAILED"


# ---------------------------------------------------------------------------
# RunResult aggregation + serialization
# ---------------------------------------------------------------------------

class TestRunResult:
    def _make_run_result(self) -> RunResult:
        cases = [
            CaseResult("G01", "s1", [True] * 5, 1.0, 200, 0),
            CaseResult("G02", "s2", [True, True, True, True, False], 4/5, 300, 0),
            CaseResult("G03", "s3", [True] * 5, 1.0, 150, 0),
        ]
        return RunResult(profile="local", timestamp="20260816T120000", cases=cases)

    def test_total_score(self):
        rr = self._make_run_result()
        expected = (1.0 + 0.8 + 1.0) / 3
        assert abs(rr.total_score - expected) < 0.001

    def test_avg_latency(self):
        rr = self._make_run_result()
        assert abs(rr.avg_latency_ms - (200 + 300 + 150) / 3) < 0.001

    def test_as_dict_is_json_serialisable(self):
        rr = self._make_run_result()
        d = rr.as_dict()
        json.dumps(d)  # must not raise

    def test_save_and_reload(self, tmp_path):
        """save_result writes valid JSON that can be reloaded."""
        from eval import RESULTS_DIR
        import eval

        orig_results_dir = eval.RESULTS_DIR
        eval.runner.RESULTS_DIR = tmp_path

        try:
            rr = self._make_run_result()
            from eval.runner import save_result
            path = save_result(rr)
            assert path.exists()
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            assert data["profile"] == "local"
            assert len(data["cases"]) == 3
        finally:
            eval.runner.RESULTS_DIR = orig_results_dir


# ---------------------------------------------------------------------------
# compare.py smoke test
# ---------------------------------------------------------------------------

class TestCompare:
    def test_compare_reads_latest_results(self, tmp_path):
        """compare._latest_result finds the most recently named file."""
        from eval import compare

        orig_dir = compare.RESULTS_DIR
        compare.RESULTS_DIR = tmp_path

        try:
            # Write two local result files; second should be picked
            d1 = {"profile": "local", "timestamp": "20260816T100000",
                  "total_score": 0.8, "avg_latency_ms": 500, "cases": []}
            d2 = {"profile": "local", "timestamp": "20260816T120000",
                  "total_score": 0.9, "avg_latency_ms": 400, "cases": []}
            (tmp_path / "local_20260816T100000.json").write_text(json.dumps(d1))
            (tmp_path / "local_20260816T120000.json").write_text(json.dumps(d2))

            result = compare._latest_result("local")
            assert result is not None
            # The lexicographically latest file name should be picked
            assert result["total_score"] == 0.9
        finally:
            compare.RESULTS_DIR = orig_dir

    def test_compare_no_results_does_not_crash(self, tmp_path):
        from eval import compare
        orig_dir = compare.RESULTS_DIR
        compare.RESULTS_DIR = tmp_path
        try:
            result = compare._latest_result("local")
            assert result is None
        finally:
            compare.RESULTS_DIR = orig_dir

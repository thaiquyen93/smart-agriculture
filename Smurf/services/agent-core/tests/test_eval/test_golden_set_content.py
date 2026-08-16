"""Tests validating content and structure of eval/golden_set.yaml."""
from __future__ import annotations

import pytest

from eval.runner import load_golden_set

VALID_TOOL_NAMES = {
    "get_device_snapshot",
    "get_metric_series",
    "get_freshness_report",
    "get_anomaly_report",
    "estimate_et0",
    "estimate_water_demand",
    "forecast_soil_moisture",
    "get_water_balance",
    "get_pump_health",
    "get_staff_roster",
    "create_irrigation_schedule",
    "create_inspection_ticket",
    "send_notification",
    "generate_report",
}


def test_golden_set_has_15_cases():
    cases = load_golden_set()
    assert len(cases) == 15
    ids = [c.id for c in cases]
    assert ids == [f"G{i:02d}" for i in range(1, 16)]


def test_required_tools_are_real_tools():
    cases = load_golden_set()
    for case in cases:
        req = case.assertions.get("required_tools", [])
        assert isinstance(req, list), f"Case {case.id}: required_tools must be a list"
        for tool in req:
            assert tool in VALID_TOOL_NAMES, (
                f"Case {case.id} specifies unknown tool: '{tool}'. Must be in {VALID_TOOL_NAMES}"
            )


def test_specific_cases_have_required_tools():
    cases = {c.id: c for c in load_golden_set()}

    # G06 must require get_pump_health and create_inspection_ticket
    assert "get_pump_health" in cases["G06"].assertions.get("required_tools", [])
    assert "create_inspection_ticket" in cases["G06"].assertions.get("required_tools", [])

    # G08 must require pump inspection
    assert "get_pump_health" in cases["G08"].assertions.get("required_tools", [])

    # G09, G10, G11 must require get_freshness_report
    for cid in ("G09", "G10", "G11"):
        assert "get_freshness_report" in cases[cid].assertions.get("required_tools", [])

    # G01, G04 must require create_irrigation_schedule
    assert "create_irrigation_schedule" in cases["G01"].assertions.get("required_tools", [])
    assert "create_irrigation_schedule" in cases["G04"].assertions.get("required_tools", [])


def test_valid_assertion_fields():
    cases = load_golden_set()
    valid_policy_outcomes = {None, "SCHEDULED", "PENDING_APPROVAL", "BLOCKED"}
    valid_verdicts = {"VERIFIED", "PARTIAL", "MISMATCH", "NO_CRASH"}

    for case in cases:
        pol = case.assertions.get("policy_outcome")
        ver = case.assertions.get("verification_verdict")
        assert pol in valid_policy_outcomes, f"Case {case.id}: invalid policy_outcome={pol}"
        assert ver in valid_verdicts, f"Case {case.id}: invalid verification_verdict={ver}"

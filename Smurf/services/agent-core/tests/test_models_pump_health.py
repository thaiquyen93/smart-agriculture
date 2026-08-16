"""Tests for the baseline PumpHealthDetector (roadmap M3.3, docs/agent-core/
05-ml-interfaces.md §3.3). Style follows tests/test_field_iot_tools.py:
build a minimal fixture by hand, call the implementation directly (no LLM
involved), assert on the dataclass fields."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from agent_core.models.baseline.pump_health import PumpHealthDetectorBaseline

BASELINE_POWER_W = 300.0
BASELINE_FLOW_LPM = 10.0
BASELINE_EFFICIENCY = BASELINE_FLOW_LPM / BASELINE_POWER_W  # ~0.0333 L/min per W


def _healthy_history(n: int = 200) -> pd.DataFrame:
    """24h of a healthy pump: power oscillates gently around 300W, flow_rate
    tracks it so efficiency stays close to BASELINE_EFFICIENCY with small,
    deterministic (non-random, reproducible) noise."""
    ts = pd.date_range("2026-08-15T00:00:00", periods=n, freq="7min")
    rows = []
    for i in range(n):
        power = BASELINE_POWER_W + 5.0 * math.sin(i * 0.3)
        flow = power * BASELINE_EFFICIENCY + 0.05 * math.cos(i * 0.3)
        rows.append({"ts": ts[i], "flow_rate": flow, "power": power})
    return pd.DataFrame(rows)


def _append_row(history: pd.DataFrame, *, flow_rate: float, power: float) -> pd.DataFrame:
    """Replace the last (most recent) row with a custom current reading,
    keeping it last by `ts`."""
    last_ts = history["ts"].max() + pd.Timedelta(minutes=7)
    new_row = pd.DataFrame([{"ts": last_ts, "flow_rate": flow_rate, "power": power}])
    return pd.concat([history, new_row], ignore_index=True)


@pytest.fixture
def detector():
    return PumpHealthDetectorBaseline()


def test_healthy_pump_is_ok(detector):
    history = _healthy_history()
    result = detector.diagnose("PUMP_01", history)

    assert result.status == "OK"
    assert result.symptom == "NONE"
    assert result.model_version == "pump-health-baseline-0.1"
    assert result.baseline_efficiency == pytest.approx(BASELINE_EFFICIENCY, rel=0.05)


def test_filter_clog_flow_low_power_normal_is_degraded_or_fault(detector):
    """Acceptance criterion M3.3: simulated filter clog -> DEGRADED (or
    FAULT) with symptom FILTER_CLOG. Power stays within +-20% of the
    learned median (pump still turning normally); flow drops to ~35% of
    what the baseline efficiency would predict at that power."""
    history = _healthy_history()
    predicted_flow_at_baseline = BASELINE_EFFICIENCY * BASELINE_POWER_W
    clogged_flow = 0.35 * predicted_flow_at_baseline
    history = _append_row(history, flow_rate=clogged_flow, power=BASELINE_POWER_W)

    result = detector.diagnose("PUMP_01", history)

    assert result.status in ("DEGRADED", "FAULT")
    assert result.symptom == "FILTER_CLOG"


def test_dry_run_high_power_no_flow(detector):
    history = _healthy_history()
    history = _append_row(history, flow_rate=0.1, power=500.0)

    result = detector.diagnose("PUMP_01", history)

    assert result.status in ("DEGRADED", "FAULT")
    assert result.symptom == "HIGH_POWER_NO_FLOW"


def test_empty_history_is_unknown(detector):
    history = pd.DataFrame(columns=["ts", "flow_rate", "power"])
    result = detector.diagnose("PUMP_01", history)

    assert result.status == "UNKNOWN"
    assert result.symptom == "UNKNOWN"
    assert result.efficiency_lpm_per_watt == 0.0
    assert result.baseline_efficiency == 0.0
    assert result.deviation_pct == 0.0


def test_pump_never_running_is_unknown(detector):
    ts = pd.date_range("2026-08-15T00:00:00", periods=20, freq="7min")
    history = pd.DataFrame({"ts": ts, "flow_rate": [0.0] * 20, "power": [5.0] * 20})

    result = detector.diagnose("PUMP_01", history)

    assert result.status == "UNKNOWN"
    assert result.symptom == "UNKNOWN"


def test_zero_mad_constant_efficiency_does_not_crash(detector):
    """Every run-sample has identical flow_rate/power -> MAD is exactly 0.
    Must not divide-by-zero/NaN; a current reading matching that same
    constant efficiency is unambiguously healthy."""
    ts = pd.date_range("2026-08-15T00:00:00", periods=20, freq="7min")
    history = pd.DataFrame(
        {"ts": ts, "flow_rate": [BASELINE_FLOW_LPM] * 20, "power": [BASELINE_POWER_W] * 20}
    )

    result = detector.diagnose("PUMP_01", history)

    assert result.status == "OK"
    assert result.symptom == "NONE"
    assert not math.isnan(result.efficiency_lpm_per_watt)
    assert not math.isnan(result.deviation_pct)


def test_missing_flow_rate_column_is_unknown_not_a_crash(detector):
    ts = pd.date_range("2026-08-15T00:00:00", periods=20, freq="7min")
    history = pd.DataFrame({"ts": ts, "power": [BASELINE_POWER_W] * 20})

    result = detector.diagnose("PUMP_01", history)

    assert result.status == "UNKNOWN"
    assert result.symptom == "UNKNOWN"

"""Baseline `PumpHealthDetector` (docs/agent-core/05-ml-interfaces.md §3.3).

Diagnoses PUMP_01 health from its own trailing-window history — no fixed
thresholds on raw flow_rate/power. Core signal is efficiency
(flow_rate / power, L/min per W), only defined while the pump is running
(power > 50W). The baseline for "normal" is the median efficiency of the
pump's own recent run-samples (self-adaptive, not a hardcoded constant);
deviation is scored with a robust z-score (MAD-based), which is resistant
to outliers unlike a plain standard-deviation z-score.

Per docs §4 "Chống cold-start": any exception here must not propagate and
crash the caller's session — `diagnose()` catches everything and degrades
to `status="UNKNOWN"`, `symptom="UNKNOWN"`, logging the failure.
"""
from __future__ import annotations

import logging

import pandas as pd

from agent_core.models.base import PumpHealthDetector, PumpHealthResult

logger = logging.getLogger(__name__)

MODEL_VERSION = "pump-health-baseline-0.1"

_RUNNING_POWER_THRESHOLD_W = 50.0
_MIN_RUN_SAMPLES = 10
_FAULT_Z = 3.5
_DEGRADED_Z = 2.0
_POWER_NORMAL_BAND = 0.2  # +-20% of median power counts as "normal power"
_FLOW_LOW_RATIO = 0.5  # flow < 50% of predicted-at-baseline counts as "low"
_FLOW_NEAR_ZERO_LPM = 0.5  # absolute threshold, L/min
_POWER_HIGH_RATIO = 1.2


def _unknown_result() -> PumpHealthResult:
    return PumpHealthResult(
        status="UNKNOWN",
        efficiency_lpm_per_watt=0.0,
        baseline_efficiency=0.0,
        deviation_pct=0.0,
        symptom="UNKNOWN",
        model_version=MODEL_VERSION,
    )


class PumpHealthDetectorBaseline(PumpHealthDetector):
    """Self-adaptive median + MAD robust-z-score baseline. See module
    docstring and docs/agent-core/05-ml-interfaces.md §3.3 for the
    algorithm this implements verbatim."""

    def diagnose(self, device_id: str, history: pd.DataFrame) -> PumpHealthResult:
        try:
            return self._diagnose(device_id, history)
        except Exception:  # noqa: BLE001 - model exceptions must never crash the agent session
            logger.exception("PumpHealthDetectorBaseline.diagnose failed for device_id=%s", device_id)
            return _unknown_result()

    def _diagnose(self, device_id: str, history: pd.DataFrame) -> PumpHealthResult:
        df_run = history[history["power"] > _RUNNING_POWER_THRESHOLD_W].dropna(
            subset=["flow_rate", "power"]
        )
        if len(df_run) < _MIN_RUN_SAMPLES:
            return _unknown_result()

        df_run = df_run.copy()
        df_run["efficiency"] = df_run["flow_rate"] / df_run["power"]
        baseline_efficiency = float(df_run["efficiency"].median())
        mad = float((df_run["efficiency"] - baseline_efficiency).abs().median())
        median_power = float(df_run["power"].median())

        history_sorted = history.sort_values("ts")
        current = history_sorted.iloc[-1]
        flow_now = float(current["flow_rate"])
        power_now = float(current["power"])

        if power_now <= _RUNNING_POWER_THRESHOLD_W:
            return PumpHealthResult(
                status="OK",
                efficiency_lpm_per_watt=0.0,
                baseline_efficiency=baseline_efficiency,
                deviation_pct=0.0,
                symptom="NONE",
                model_version=MODEL_VERSION,
            )

        efficiency_now = flow_now / power_now
        if mad > 1e-9:
            z = 0.6745 * (efficiency_now - baseline_efficiency) / mad
        else:
            if abs(efficiency_now - baseline_efficiency) < 1e-9:
                z = 0.0
            else:
                z = 10.0 if efficiency_now < baseline_efficiency else -10.0

        deviation_pct = (
            (efficiency_now - baseline_efficiency) / baseline_efficiency * 100.0
            if baseline_efficiency > 1e-9
            else 0.0
        )

        if abs(z) > _FAULT_Z:
            status = "FAULT"
        elif abs(z) > _DEGRADED_Z:
            status = "DEGRADED"
        else:
            status = "OK"

        power_normal = abs(power_now - median_power) <= _POWER_NORMAL_BAND * median_power
        predicted_flow_at_baseline = baseline_efficiency * power_now
        flow_low = flow_now < _FLOW_LOW_RATIO * predicted_flow_at_baseline
        flow_near_zero = flow_now < _FLOW_NEAR_ZERO_LPM
        power_high = power_now > median_power * _POWER_HIGH_RATIO

        if status == "OK":
            symptom = "NONE"
        elif flow_near_zero and power_high:
            symptom = "HIGH_POWER_NO_FLOW"
        elif flow_low and power_normal:
            symptom = "FILTER_CLOG"
        else:
            symptom = "INTERMITTENT"

        return PumpHealthResult(
            status=status,
            efficiency_lpm_per_watt=efficiency_now,
            baseline_efficiency=baseline_efficiency,
            deviation_pct=deviation_pct,
            symptom=symptom,
            model_version=MODEL_VERSION,
        )

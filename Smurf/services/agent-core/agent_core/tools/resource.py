"""Resource Agent tools (water balance, pump health, staff roster).

Follows docs/agent-core/02-agents-and-tools.md §C.4.
Checks feasibility constraints: tank level, pump status, staff availability.
"""
from __future__ import annotations

import time

from agent_core.config import Settings
from agent_core.devices import DeviceId, Metric
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.state.freshness import Freshness, classify, worse
from agent_core.state.store import FarmStateStore

# M2 fixed baseline for get_pump_health (docs/agent-core/02-agents-and-tools.md
# §C.4). M3 replaces this with a self-adaptive rolling-24h median/MAD per pump
# (05-ml-interfaces.md §3.3) — needs pandas/sklearn, not yet in requirements.txt.
_PUMP_POWER_IDLE_THRESHOLD_W = 50.0  # below this the pump isn't running; efficiency is undefined, not a fault
_PUMP_BASELINE_EFFICIENCY_LPM_PER_W = 8.0
_PUMP_FAULT_DEVIATION_PCT = 50.0
_PUMP_DEGRADED_DEVIATION_PCT = 25.0


def _error(code: str, message: str, *, retryable: bool = False, suggested_action: str = "NONE") -> dict:
    return {
        "ok": False,
        "error_code": code,
        "message": message,
        "retryable": retryable,
        "suggested_action": suggested_action,
    }


def get_water_balance(
    store: FarmStateStore,
    ledger: EvidenceLedger,
    settings: Settings,
    *,
    required_liters: float,
) -> dict:
    """Check if tank has enough water for required volume.

    Returns: {ok, tank_level_pct, available_liters, sufficient, evidence_id, markdown}
    """
    now = time.time()
    tank_reading = store.latest(DeviceId.TANK_01, Metric.LEVEL)

    if not tank_reading:
        return _error(
            "INSUFFICIENT_DATA",
            "Không có dữ liệu mực bồn.",
            suggested_action="CHECK_TANK_SENSOR",
        )

    tank_age = now - tank_reading.observed_at
    tank_freshness = classify(tank_age, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec)

    if tank_freshness == Freshness.OFFLINE:
        return _error(
            "STALE_DATA",
            f"Dữ liệu mực bồn quá cũ ({int(tank_age)}s).",
            suggested_action="WAIT_FOR_FRESH_DATA",
        )

    tank_level_pct = tank_reading.value
    tank_capacity_liters = 2000.0  # Assume 2000L tank
    available_liters = tank_capacity_liters * (tank_level_pct / 100.0)

    sufficient = available_liters >= required_liters

    evidence = ledger.record(
        device_id=DeviceId.TANK_01,
        metric=Metric.LEVEL.value,
        value_text=f"{tank_level_pct:.1f}",
        unit="%",
        observed_at=tank_reading.observed_at,
        age_seconds=tank_age,
        freshness=tank_freshness,
        source_topic=tank_reading.source_topic,
        window_type="NONE",
    )

    if sufficient:
        markdown = f"**Mực bồn:** {tank_level_pct:.1f}% ({available_liters:.0f} L). Đủ cho {required_liters:.0f} L."
    else:
        markdown = (
            f"**Mực bồn:** {tank_level_pct:.1f}% ({available_liters:.0f} L). "
            f"⚠️ Không đủ cho {required_liters:.0f} L."
        )

    return {
        "ok": True,
        "tank_level_pct": tank_level_pct,
        "available_liters": available_liters,
        "sufficient": sufficient,
        "evidence_id": evidence.evidence_id,
        "markdown": markdown,
    }


def get_pump_health(
    store: FarmStateStore,
    ledger: EvidenceLedger,
    settings: Settings,
    *,
    pump_id: str,
) -> dict:
    """Diagnose pump health from PUMP_01's flow_rate/power ratio — "chẩn đoán
    trên tỉ số, không phải ngưỡng tuyệt đối" (docs/agent-core/02-agents-and-tools.md
    §C.4). There is no separate VALVE/pump-status sensor in the 6-device
    registry (agent_core.devices) — PUMP_01 only ever emits flow_rate+power.

    M2 baseline: fixed nominal efficiency + deviation_pct thresholds (see
    module-level constants above). M3 replaces the fixed baseline with a
    self-adaptive rolling-24h median/MAD per pump (05-ml-interfaces.md §3.3).

    Returns: {ok, status, efficiency_lpm_per_watt, baseline_efficiency,
              deviation_pct, symptom, operational, model_version, evidence_id, markdown}
    """
    now = time.time()

    flow_reading = store.latest(DeviceId.PUMP_01, Metric.FLOW_RATE)
    power_reading = store.latest(DeviceId.PUMP_01, Metric.POWER)

    if not flow_reading or not power_reading:
        return _error(
            "INSUFFICIENT_DATA",
            f"Không có dữ liệu bơm {pump_id}.",
            suggested_action="CHECK_PUMP_SENSOR",
        )

    flow_age = now - flow_reading.observed_at
    power_age = now - power_reading.observed_at
    freshness = worse(
        classify(flow_age, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec),
        classify(power_age, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec),
    )

    if freshness == Freshness.OFFLINE:
        return _error(
            "STALE_DATA",
            f"Dữ liệu bơm quá cũ (flow: {int(flow_age)}s, power: {int(power_age)}s).",
            suggested_action="WAIT_FOR_FRESH_DATA",
        )

    flow_rate = flow_reading.value
    power = power_reading.value

    if power <= _PUMP_POWER_IDLE_THRESHOLD_W:
        # Pump not running — efficiency is undefined, not itself a fault.
        status, symptom, efficiency, deviation_pct = "OK", "NONE", 0.0, 0.0
    else:
        efficiency = flow_rate / power
        deviation_pct = (
            (efficiency - _PUMP_BASELINE_EFFICIENCY_LPM_PER_W) / _PUMP_BASELINE_EFFICIENCY_LPM_PER_W * 100.0
        )
        abs_deviation = abs(deviation_pct)
        if abs_deviation > _PUMP_FAULT_DEVIATION_PCT:
            status = "FAULT"
        elif abs_deviation > _PUMP_DEGRADED_DEVIATION_PCT:
            status = "DEGRADED"
        else:
            status = "OK"

        if flow_rate < 0.5:
            symptom = "HIGH_POWER_NO_FLOW"  # nghi chạy khô
        elif deviation_pct < -_PUMP_DEGRADED_DEVIATION_PCT:
            symptom = "LOW_FLOW_NORMAL_POWER"  # nghi tắc lọc
        else:
            symptom = "NONE"

    operational = status != "FAULT"

    evidence = ledger.record(
        device_id=DeviceId.PUMP_01,
        metric="pump_health",
        value_text=status,
        unit="",
        observed_at=min(flow_reading.observed_at, power_reading.observed_at),
        age_seconds=max(flow_age, power_age),
        freshness=freshness,
        source_topic=flow_reading.source_topic,
        window_type="NONE",
    )

    markdown = (
        f"**Bơm {pump_id}:** {status} (hiệu suất {efficiency:.2f} L/min/W so với nền "
        f"{_PUMP_BASELINE_EFFICIENCY_LPM_PER_W:.2f}, lệch {deviation_pct:+.0f}%). "
        f"{'✅ Hoạt động bình thường.' if operational else f'⚠️ Cần kiểm tra — {symptom}.'}"
    )

    return {
        "ok": True,
        "status": status,
        "efficiency_lpm_per_watt": efficiency,
        "baseline_efficiency": _PUMP_BASELINE_EFFICIENCY_LPM_PER_W,
        "deviation_pct": deviation_pct,
        "symptom": symptom,
        "operational": operational,
        "model_version": "baseline-fixed-threshold-v1",
        "evidence_id": evidence.evidence_id,
        "markdown": markdown,
    }


def get_staff_roster(
    store: FarmStateStore,
    ledger: EvidenceLedger,
    settings: Settings,
    *,
    date_iso: str,
    skill_required: str = "NONE",
) -> dict:
    """Get available field staff for given date.

    M2: mock data (hardcoded roster). M3: read from staff_schedule DB table.
    Returns: {ok, available_staff, markdown}
    """
    # Mock roster for M2
    staff_roster = [
        {"staff_id": "STF_01", "name": "Nguyễn Văn A", "skills": ["IRRIGATION", "SENSOR_REPAIR"]},
        {"staff_id": "STF_02", "name": "Nguyễn Văn B", "skills": ["SENSOR_REPAIR", "PUMP_MAINTENANCE"]},
        {"staff_id": "STF_03", "name": "Trần Thị C", "skills": ["IRRIGATION", "CROP_INSPECTION"]},
    ]

    if skill_required != "NONE":
        available = [s for s in staff_roster if skill_required in s["skills"]]
    else:
        available = staff_roster

    # Create mock evidence (no actual sensor reading for staff roster)
    evidence = ledger.record(
        device_id=DeviceId.WEATHER_01,  # Placeholder device — no real sensor backs a staff roster lookup
        metric="staff_roster",
        value_text=f"{len(available)} available",
        unit="staff",
        observed_at=time.time(),
        age_seconds=0,
        freshness=Freshness.FRESH,
        source_topic="staff_db",
        window_type="NONE",
    )

    staff_names = ", ".join(s["name"] for s in available)
    markdown = f"**Nhân viên khả dụng ({date_iso}):** {len(available)} người. {staff_names}."

    return {
        "ok": True,
        "available_staff": available,
        "evidence_id": evidence.evidence_id,
        "markdown": markdown,
    }

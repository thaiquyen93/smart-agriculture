"""Resource Agent tools (water balance, pump health, staff roster).

Follows docs/agent-core/02-agents-and-tools.md §C.4.
Checks feasibility constraints: tank level, pump status, staff availability.
"""
from __future__ import annotations

import time

from agent_core.config import Settings
from agent_core.devices import DeviceId, Metric
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.state.freshness import Freshness, classify
from agent_core.state.store import FarmStateStore


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
    tank_reading = store.latest(DeviceId.TANK_01, Metric.TANK_LEVEL)

    if not tank_reading:
        return _error(
            "INSUFFICIENT_DATA",
            "Không có dữ liệu mực bồn.",
            suggested_action="CHECK_TANK_SENSOR",
        )

    tank_age = now - tank_reading.observed_at
    tank_freshness = classify(tank_age, settings.freshness_fresh_sec, settings.freshness_stale_sec)

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
        metric=Metric.TANK_LEVEL,
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
    """Check pump operational status.

    Returns: {ok, status, operational, evidence_id, markdown}
    """
    now = time.time()

    # M2: simplified - use VALVE status as pump proxy (real deployment has separate pump sensors)
    valve_reading = store.latest(DeviceId.VALVE_ZONE_A, Metric.VALVE_STATUS)

    if not valve_reading:
        return _error(
            "INSUFFICIENT_DATA",
            f"Không có dữ liệu bơm {pump_id}.",
            suggested_action="CHECK_PUMP_SENSOR",
        )

    valve_age = now - valve_reading.observed_at
    valve_freshness = classify(valve_age, settings.freshness_fresh_sec, settings.freshness_stale_sec)

    if valve_freshness == Freshness.OFFLINE:
        return _error(
            "STALE_DATA",
            f"Dữ liệu bơm quá cũ ({int(valve_age)}s).",
            suggested_action="WAIT_FOR_FRESH_DATA",
        )

    # valve_status: 0=CLOSED, 1=OPEN
    status = "OK" if valve_reading.value >= 0 else "FAULT"
    operational = status == "OK"

    evidence = ledger.record(
        device_id=DeviceId.VALVE_ZONE_A,
        metric=Metric.VALVE_STATUS,
        value_text=status,
        unit="",
        observed_at=valve_reading.observed_at,
        age_seconds=valve_age,
        freshness=valve_freshness,
        source_topic=valve_reading.source_topic,
        window_type="NONE",
    )

    markdown = f"**Bơm {pump_id}:** {status}. {'✅ Hoạt động bình thường.' if operational else '⚠️ Lỗi.'}"

    return {
        "ok": True,
        "status": status,
        "operational": operational,
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
        device_id=DeviceId.TEMP_ZONE_A,  # Placeholder device
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

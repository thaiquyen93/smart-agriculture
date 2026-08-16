"""Agronomy Agent tools (water demand, ET0, soil moisture forecast).

Follows docs/agent-core/02-agents-and-tools.md §C.3.
Uses simplified ML models (Penman-Monteith for ET0, physics-based decay).
Full ML models (gradient boosting, LSTM) are M3 scope (05-ml-interfaces.md).
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta

from agent_core.config import Settings
from agent_core.devices import DeviceId, Metric
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.state.freshness import Freshness, classify
from agent_core.state.store import FarmStateStore
from agent_core.timeutil import to_iso


def _error(code: str, message: str, *, retryable: bool = False, suggested_action: str = "NONE") -> dict:
    return {
        "ok": False,
        "error_code": code,
        "message": message,
        "retryable": retryable,
        "suggested_action": suggested_action,
    }


def estimate_et0(
    store: FarmStateStore,
    ledger: EvidenceLedger,
    settings: Settings,
    *,
    zone: str,
    date_iso: str,
) -> dict:
    """Estimate reference evapotranspiration ET0 (mm/day) using simplified Penman-Monteith.

    M2 uses physics-based approximation. M3 will replace with trained model.
    Returns: {ok, et0_mm_per_day, evidence_id, markdown}
    """
    now = time.time()

    temp_reading = store.latest(DeviceId.WEATHER_01, Metric.TEMPERATURE)
    lux_reading = store.latest(DeviceId.SUN_01, Metric.LUX)

    if not temp_reading or not lux_reading:
        return _error(
            "INSUFFICIENT_DATA",
            f"Thiếu dữ liệu nhiệt độ hoặc ánh sáng cho zone {zone}.",
            suggested_action="CHECK_SENSORS",
        )

    temp_age = now - temp_reading.observed_at
    lux_age = now - lux_reading.observed_at
    temp_freshness = classify(temp_age, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec)
    lux_freshness = classify(lux_age, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec)

    if temp_freshness == Freshness.OFFLINE or lux_freshness == Freshness.OFFLINE:
        return _error(
            "STALE_DATA",
            f"Dữ liệu cảm biến quá cũ (temp: {int(temp_age)}s, lux: {int(lux_age)}s).",
            suggested_action="WAIT_FOR_FRESH_DATA",
        )

    temp_c = temp_reading.value
    lux = lux_reading.value

    # Simplified Penman-Monteith: ET0 ≈ 0.0023 * (T_mean + 17.8) * sqrt(T_max - T_min) * Ra
    # For simplicity: assume T_mean ≈ T_current, delta_T ≈ 10°C, Ra ≈ f(lux)
    ra_factor = min(lux / 50000, 1.5)  # Normalize lux to solar radiation proxy
    et0_mm = 0.0023 * (temp_c + 17.8) * math.sqrt(10) * ra_factor

    et0_mm = max(0.5, min(et0_mm, 12.0))  # Clamp to realistic range

    evidence = ledger.record(
        device_id=DeviceId.WEATHER_01,
        metric="et0_estimated",
        value_text=f"{et0_mm:.2f}",
        unit="mm/day",
        observed_at=now,
        age_seconds=0,
        freshness=Freshness.FRESH,
        source_topic="computed",
        window_type="NONE",
    )

    markdown = f"**ET0 ước tính:** {et0_mm:.2f} mm/ngày (dựa trên T={temp_c:.1f}°C, Lux={lux:.0f})"

    return {
        "ok": True,
        "et0_mm_per_day": et0_mm,
        "evidence_id": evidence.evidence_id,
        "markdown": markdown,
    }


def estimate_water_demand(
    store: FarmStateStore,
    ledger: EvidenceLedger,
    settings: Settings,
    *,
    zone: str,
    crop_type: str,
    horizon_hours: int,
) -> dict:
    """Estimate water demand (liters) for next `horizon_hours`.

    Uses ET0 + crop coefficient + area. M2: simplified. M3: trained model.
    Returns: {ok, volume_liters, volume_min, volume_max, evidence_id, markdown}
    """
    et0_result = estimate_et0(store, ledger, settings, zone=zone, date_iso=to_iso(time.time()))
    if not et0_result["ok"]:
        return et0_result

    et0_mm = et0_result["et0_mm_per_day"]

    soil_reading = store.latest(DeviceId.SOIL_01, Metric.SOIL_MOISTURE)
    if not soil_reading:
        return _error("INSUFFICIENT_DATA", "Thiếu dữ liệu độ ẩm đất.", suggested_action="CHECK_SENSORS")

    current_moisture = soil_reading.value
    target_moisture = 35.0  # Optimal for most crops
    moisture_deficit = max(0, target_moisture - current_moisture)

    # Simplified: 1% moisture deficit ≈ 10 L/m² for 100m² zone
    area_m2 = 100.0
    kc = 1.0 if crop_type == "Cam" else 0.8  # Crop coefficient

    # Water needed = ET0 * Kc * area * (horizon_days) + deficit補填
    horizon_days = horizon_hours / 24.0
    et_loss_liters = et0_mm * kc * area_m2 * horizon_days / 10.0  # mm → cm → L
    deficit_liters = moisture_deficit * area_m2 * 10.0

    volume_liters = et_loss_liters + deficit_liters
    volume_min = volume_liters * 0.85
    volume_max = volume_liters * 1.15

    evidence = ledger.record(
        device_id=DeviceId.SOIL_01,
        metric="water_demand_estimated",
        value_text=f"{volume_liters:.1f}",
        unit="L",
        observed_at=time.time(),
        age_seconds=0,
        freshness=Freshness.FRESH,
        source_topic="computed",
        window_type="NONE",
    )

    markdown = (
        f"**Nhu cầu nước:** {volume_liters:.0f} L ({volume_min:.0f}–{volume_max:.0f} L) "
        f"cho {horizon_hours}h tới. "
        f"ET0={et0_mm:.1f} mm/ngày, thiếu ẩm={moisture_deficit:.1f}%."
    )

    return {
        "ok": True,
        "volume_liters": volume_liters,
        "volume_min": volume_min,
        "volume_max": volume_max,
        "evidence_id": evidence.evidence_id,
        "markdown": markdown,
    }


def forecast_soil_moisture(
    store: FarmStateStore,
    ledger: EvidenceLedger,
    settings: Settings,
    *,
    zone: str,
    horizon_hours: int,
) -> dict:
    """Forecast soil moisture % after `horizon_hours` without irrigation.

    M2: physics-based decay. M3: LSTM model (05-ml-interfaces.md §3.2).
    Returns: {ok, forecast_pct, confidence, evidence_id, markdown}
    """
    soil_reading = store.latest(DeviceId.SOIL_01, Metric.SOIL_MOISTURE)
    temp_reading = store.latest(DeviceId.WEATHER_01, Metric.TEMPERATURE)
    lux_reading = store.latest(DeviceId.SUN_01, Metric.LUX)

    if not soil_reading or not temp_reading or not lux_reading:
        return _error("INSUFFICIENT_DATA", "Thiếu dữ liệu cảm biến để dự báo.", suggested_action="CHECK_SENSORS")

    current_moisture = soil_reading.value
    temp_c = temp_reading.value
    lux = lux_reading.value

    # Simplified decay model: moisture decreases by (ET0 * time) / area_depth
    et0_result = estimate_et0(store, ledger, settings, zone=zone, date_iso=to_iso(time.time()))
    if not et0_result["ok"]:
        return et0_result

    et0_mm = et0_result["et0_mm_per_day"]
    horizon_days = horizon_hours / 24.0

    # Assume soil depth 30cm → 1mm ET ≈ 0.33% moisture loss
    moisture_loss_pct = et0_mm * horizon_days * 0.33

    forecast_pct = max(15.0, current_moisture - moisture_loss_pct)  # Clamp at 15% (wilting point)

    confidence = "CONFIDENT" if forecast_pct > 25 else "TENTATIVE"

    evidence = ledger.record(
        device_id=DeviceId.SOIL_01,
        metric="soil_moisture_forecast",
        value_text=f"{forecast_pct:.1f}",
        unit="%",
        observed_at=time.time(),
        age_seconds=0,
        freshness=Freshness.FRESH,
        source_topic="computed",
        window_type="NONE",
    )

    markdown = (
        f"**Dự báo độ ẩm:** {forecast_pct:.1f}% sau {horizon_hours}h (hiện tại {current_moisture:.1f}%). "
        f"Suy giảm dự kiến {moisture_loss_pct:.1f}% do ET0={et0_mm:.1f} mm/ngày."
    )

    return {
        "ok": True,
        "forecast_pct": forecast_pct,
        "confidence": confidence,
        "evidence_id": evidence.evidence_id,
        "markdown": markdown,
    }

"""Shared device/metric enums and the device→metric→unit registry.

Single source of truth for which of the 6 Track B devices exist, which
metrics each one legitimately emits, and what unit each metric is in.
`docs/agent-core/02-agents-and-tools.md` C.1 defines the enums; it does NOT
give a full unit table (only 3 examples) — the units below are this
project's own explicit choice, easy to correct if BTC publishes a different
convention. Everything downstream (Farm State Store, Kafka parser, the 4
Field IoT tools) imports from here instead of repeating string literals.
"""
from __future__ import annotations

from enum import Enum


class DeviceId(str, Enum):
    SOIL_01 = "SOIL_01"
    WEATHER_01 = "WEATHER_01"
    PUMP_01 = "PUMP_01"
    PH_01 = "PH_01"
    TANK_01 = "TANK_01"
    SUN_01 = "SUN_01"


class Metric(str, Enum):
    SOIL_MOISTURE = "soil_moisture"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    FLOW_RATE = "flow_rate"
    POWER = "power"
    PH = "ph"
    LEVEL = "level"
    LUX = "lux"


class Freshness(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    OFFLINE = "OFFLINE"


class WindowType(str, Enum):
    NONE = "NONE"  # straight from topic_raw, not a windowed aggregate
    TUMBLING_1M = "TUMBLING_1M"
    SLIDING_10M = "SLIDING_10M"
    HOURLY_1H = "HOURLY_1H"


ZONE = "ZONE_A"

# device_id -> {metric: unit}. Order matters for markdown table rendering
# (get_device_snapshot lists metrics in this order).
DEVICE_METRICS: dict[DeviceId, dict[Metric, str]] = {
    DeviceId.SOIL_01: {Metric.SOIL_MOISTURE: "%", Metric.TEMPERATURE: "°C"},
    DeviceId.WEATHER_01: {Metric.TEMPERATURE: "°C", Metric.HUMIDITY: "%"},
    DeviceId.PUMP_01: {Metric.FLOW_RATE: "L/min", Metric.POWER: "W"},
    DeviceId.PH_01: {Metric.PH: "pH"},
    DeviceId.TANK_01: {Metric.LEVEL: "%"},
    DeviceId.SUN_01: {Metric.LUX: "lux"},
}

ALL_DEVICE_IDS: tuple[DeviceId, ...] = tuple(DEVICE_METRICS.keys())


def metrics_for(device_id: DeviceId) -> dict[Metric, str]:
    """Metrics + units this device is expected to emit. Empty dict for an
    unknown device_id (callers should already have validated against
    DeviceId before calling this — this is just a safe default)."""
    return DEVICE_METRICS.get(device_id, {})


def unit_for(device_id: DeviceId, metric: Metric) -> str:
    return DEVICE_METRICS.get(device_id, {}).get(metric, "")

"""Dataclasses held by the Farm State Store. No business logic here —
just shapes. See `agent_core.state.store.FarmStateStore` for behavior.
"""
from __future__ import annotations

from dataclasses import dataclass

from agent_core.devices import DeviceId, Metric, WindowType


@dataclass(frozen=True)
class DeviceReading:
    """The latest known value of one (device_id, metric) pair, as observed
    on `topic_raw` (WindowType.NONE) — see design decision #2 in the M1
    plan: topic_raw drives "current value", topic_p/h drive series only."""

    device_id: DeviceId
    metric: Metric
    value: float
    unit: str
    observed_at: float  # epoch seconds
    source_topic: str


@dataclass(frozen=True)
class MetricSeriesPoint:
    """One aggregated window point, from topic_p or topic_h."""

    window_type: WindowType
    window_end: float  # epoch seconds — the point's timestamp
    avg: float
    min: float
    max: float
    trend: float | None


@dataclass(frozen=True)
class AnomalyEvent:
    """One rule-based anomaly from a topic_p/topic_h window's `anomalies`
    array (see aggregators.py) — not an ML model output (that's M3)."""

    anomaly_type: str
    device_id: DeviceId
    metric: str
    severity: str  # "HIGH" | "WARNING" as emitted by aggregators.py
    value: float
    message: str
    detected_at: float  # epoch seconds, == window_end

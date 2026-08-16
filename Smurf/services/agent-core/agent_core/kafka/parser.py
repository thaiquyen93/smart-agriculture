"""Normalizes raw Kafka message payloads (topic_raw / topic_p / topic_h)
into agent_core.state.models before they reach the Farm State Store.

Deliberately tolerant, not strict — this repo has multiple producers
feeding these topics (farm_simulator.py + mqtt_bridge.py + simulator/main.py,
see services/ingestion-stream-engine), and field-shape has already drifted
once (the temp_avg bug). Unknown device_ids or missing metrics are skipped
and logged, never raised — a bad/foreign message must not crash the
consumer thread or corrupt state for the other 6 known devices.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from agent_core.devices import ALL_DEVICE_IDS, DeviceId, Metric, metrics_for
from agent_core.state.models import AnomalyEvent, DeviceReading, MetricSeriesPoint

logger = logging.getLogger(__name__)

_DEVICE_IDS_BY_VALUE = {d.value: d for d in ALL_DEVICE_IDS}
_METRICS_BY_VALUE = {m.value: m for m in Metric}


def _resolve_device_id(payload: dict) -> DeviceId | None:
    """Same fallback chain used elsewhere in the repo (see
    services/web-backend/src/modules/kafka/kafka.service.ts): device_id,
    then device_code, then station_id. Returns None for anything outside
    the 6-device enum (e.g. STN_HN_01 from the unrelated weather-station
    simulator) — caller is expected to skip, not raise."""
    raw_id = payload.get("device_id") or payload.get("device_code") or payload.get("station_id")
    if raw_id is None:
        return None
    return _DEVICE_IDS_BY_VALUE.get(str(raw_id))


def parse_raw(payload: dict, *, source_topic: str = "topic_raw") -> list[DeviceReading]:
    """topic_raw: flat payload, one message = one device's instantaneous
    reading. Extracts every field name that matches a known Metric for that
    device; ignores everything else (status strings, lat/lon, timestamps).
    """
    device_id = _resolve_device_id(payload)
    if device_id is None:
        logger.debug("parse_raw: unknown device in payload, skipping: %r", payload.get("device_id"))
        return []

    observed_at = payload.get("event_time") or payload.get("timestamp") or payload.get("created_at")
    if observed_at is None:
        logger.debug("parse_raw: no timestamp field for %s, skipping", device_id.value)
        return []

    known_metrics = metrics_for(device_id)
    readings: list[DeviceReading] = []
    for metric, unit in known_metrics.items():
        value = payload.get(metric.value)
        if value is None:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue  # e.g. PUMP_01.status is "ON"/"OFF", not a metric value
        readings.append(
            DeviceReading(
                device_id=device_id,
                metric=metric,
                value=numeric_value,
                unit=unit,
                observed_at=float(observed_at),
                source_topic=source_topic,
            )
        )
    return readings


@dataclass(frozen=True)
class ParsedWindow:
    device_id: DeviceId
    window_type: str  # kept as the raw string from the payload — see note below
    window_end: float
    points: list[MetricSeriesPoint]
    metric_by_point: list[Metric]
    anomalies: list[AnomalyEvent]


def parse_window(payload: dict) -> ParsedWindow | None:
    """topic_p / topic_h: one message = one device's aggregated window.
    `metrics` is a DYNAMIC dict (`{field}_avg/min/max/trend` for whatever
    numeric fields existed in that window's raw records — see
    aggregators.py; there is no fixed key like `temp_avg`). window_type is
    passed through as-is (not string-matched against an enum) — the label
    format has already drifted once between docs and a stale docstring in
    windowing.py, so treat it as an opaque tag, not something to validate.
    No separate `source_topic` param is needed: `window_type` already
    disambiguates topic_p (`TUMBLING_1M`/`SLIDING_10M`) from topic_h
    (`HOURLY_1H`) — see agent_core.tools.field_iot._source_topic_for.
    """
    device_id = _resolve_device_id(payload)
    if device_id is None:
        logger.debug("parse_window: unknown device in payload, skipping: %r", payload.get("device_id"))
        return None

    window_end = payload.get("window_end") or payload.get("created_at")
    if window_end is None:
        logger.debug("parse_window: no window_end for %s, skipping", device_id.value)
        return None
    window_end = float(window_end)

    known_metrics = metrics_for(device_id)
    metrics_raw: dict = payload.get("metrics") or {}
    points: list[MetricSeriesPoint] = []
    metric_by_point: list[Metric] = []
    for metric in known_metrics:
        avg = metrics_raw.get(f"{metric.value}_avg")
        if avg is None:
            continue
        points.append(
            MetricSeriesPoint(
                window_type=payload.get("window_type", "NONE"),
                window_end=window_end,
                avg=float(avg),
                min=float(metrics_raw.get(f"{metric.value}_min", avg)),
                max=float(metrics_raw.get(f"{metric.value}_max", avg)),
                trend=(
                    float(metrics_raw[f"{metric.value}_trend"])
                    if metrics_raw.get(f"{metric.value}_trend") is not None
                    else None
                ),
            )
        )
        metric_by_point.append(metric)

    anomalies: list[AnomalyEvent] = []
    for raw_anomaly in payload.get("anomalies") or []:
        metric_str = raw_anomaly.get("metric", "")
        anomalies.append(
            AnomalyEvent(
                anomaly_type=raw_anomaly.get("type", "UNKNOWN"),
                device_id=device_id,
                metric=metric_str,
                severity=raw_anomaly.get("severity", "WARNING"),
                value=float(raw_anomaly.get("val", 0.0)),
                message=raw_anomaly.get("msg", ""),
                detected_at=window_end,
            )
        )

    return ParsedWindow(
        device_id=device_id,
        window_type=payload.get("window_type", "NONE"),
        window_end=window_end,
        points=points,
        metric_by_point=metric_by_point,
        anomalies=anomalies,
    )

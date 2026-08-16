"""FarmStateStore — the single source of truth for device state
(roadmap M1.1). Two layers: an in-memory dict every tool/API reads from
(hot path, no I/O), mirrored write-through into SQLite so state survives a
restart (`services/agent-core/data/farm_state.db`, gitignored via `*.db`).

Design decision (see M1 plan): `topic_raw` drives "current value" (via
`update_from_raw`); `topic_p`/`topic_h` only feed the metric-series buffer
and the anomaly buffer (via `update_from_window`) — they never overwrite
the "latest reading" shown by get_device_snapshot.

Thread-safety: a single `threading.Lock` guards all mutation. Writes come
from the Kafka consumer's daemon thread; reads come from FastAPI request
threads and (later) tool calls — both must see a consistent snapshot.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from collections import deque
from pathlib import Path

from dataclasses import dataclass

from agent_core.devices import ALL_DEVICE_IDS, DeviceId, Freshness, Metric, metrics_for
from agent_core.kafka.parser import parse_raw, parse_window
from agent_core.state.freshness import RANK, classify
from agent_core.state.models import AnomalyEvent, DeviceReading, MetricSeriesPoint

# Bound memory: at most this many aggregated points per (device_id, metric,
# window_type). get_metric_series only ever returns <=24 downsampled points
# anyway (02-agents-and-tools.md C.2.2) — this is just the raw retention
# buffer feeding that downsample.
MAX_SERIES_POINTS = 1500
MAX_ANOMALIES = 500

@dataclass(frozen=True)
class DeviceFreshnessSummary:
    """Device-level freshness = worst (highest-rank) freshness across every
    metric that device is expected to emit. Centralized here because the
    naive version of this reduction (seed `worst` with Freshness.FRESH, only
    overwrite on strictly-worse) has a real bug: a uniformly-FRESH device
    never satisfies `rank(FRESH) > rank(FRESH)`, so `worst_age`/
    `worst_reading` stay None even though the device is fine. Every caller
    that needs per-device freshness (GET /health, GET /api/v1/state/farm,
    get_freshness_report) should use this instead of re-deriving it."""

    device_id: DeviceId
    worst: Freshness
    worst_age: float | None
    worst_reading: DeviceReading | None
    per_metric: list[tuple[Metric, DeviceReading | None, float | None, Freshness]]


_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS latest_readings (
    device_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    observed_at REAL NOT NULL,
    source_topic TEXT NOT NULL,
    PRIMARY KEY (device_id, metric)
);
"""


class FarmStateStore:
    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self._lock = threading.Lock()
        self._latest: dict[tuple[DeviceId, Metric], DeviceReading] = {}
        self._series: dict[tuple[DeviceId, Metric, str], deque[MetricSeriesPoint]] = {}
        self._anomalies: deque[AnomalyEvent] = deque(maxlen=MAX_ANOMALIES)
        self._earliest_window_seen: float | None = None  # for MODEL_COLD_START detection

        self._db_path = Path(db_path) if db_path else None
        self._conn: sqlite3.Connection | None = None
        if self._db_path is not None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.execute(_DB_SCHEMA)
            self._conn.commit()
            self._load_from_db()

    def _load_from_db(self) -> None:
        assert self._conn is not None
        rows = self._conn.execute(
            "SELECT device_id, metric, value, unit, observed_at, source_topic FROM latest_readings"
        ).fetchall()
        for device_id_s, metric_s, value, unit, observed_at, source_topic in rows:
            try:
                device_id = DeviceId(device_id_s)
                metric = Metric(metric_s)
            except ValueError:
                continue
            self._latest[(device_id, metric)] = DeviceReading(
                device_id=device_id,
                metric=metric,
                value=value,
                unit=unit,
                observed_at=observed_at,
                source_topic=source_topic,
            )

    def _persist_latest(self, reading: DeviceReading) -> None:
        if self._conn is None:
            return
        self._conn.execute(
            """INSERT INTO latest_readings (device_id, metric, value, unit, observed_at, source_topic)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(device_id, metric) DO UPDATE SET
                   value=excluded.value, unit=excluded.unit,
                   observed_at=excluded.observed_at, source_topic=excluded.source_topic""",
            (
                reading.device_id.value,
                reading.metric.value,
                reading.value,
                reading.unit,
                reading.observed_at,
                reading.source_topic,
            ),
        )
        self._conn.commit()

    # --- ingestion -------------------------------------------------------

    def update_from_raw(self, payload: dict) -> list[DeviceReading]:
        readings = parse_raw(payload)
        with self._lock:
            for reading in readings:
                key = (reading.device_id, reading.metric)
                existing = self._latest.get(key)
                if existing is not None and existing.observed_at > reading.observed_at:
                    continue  # out-of-order message, keep the newer one
                self._latest[key] = reading
                self._persist_latest(reading)
        return readings

    def update_from_window(self, payload: dict) -> None:
        parsed = parse_window(payload)
        if parsed is None:
            return
        with self._lock:
            if self._earliest_window_seen is None:
                self._earliest_window_seen = parsed.window_end
            for metric, point in zip(parsed.metric_by_point, parsed.points):
                key = (parsed.device_id, metric, parsed.window_type)
                buf = self._series.setdefault(key, deque(maxlen=MAX_SERIES_POINTS))
                buf.append(point)
            for anomaly in parsed.anomalies:
                self._anomalies.append(anomaly)

    # --- reads -------------------------------------------------------------

    def latest(self, device_id: DeviceId, metric: Metric) -> DeviceReading | None:
        with self._lock:
            return self._latest.get((device_id, metric))

    def latest_for_device(self, device_id: DeviceId) -> dict[Metric, DeviceReading | None]:
        """Every metric this device is expected to emit, `None` if never
        observed — callers must render that as an OFFLINE row, not skip it
        (02-agents-and-tools.md poka-yoke: never a silent gap)."""
        with self._lock:
            return {metric: self._latest.get((device_id, metric)) for metric in metrics_for(device_id)}

    def series(
        self, device_id: DeviceId, metric: Metric, *, window_type: str, since: float | None = None
    ) -> list[MetricSeriesPoint]:
        with self._lock:
            buf = self._series.get((device_id, metric, window_type), deque())
            points = list(buf)
        if since is not None:
            points = [p for p in points if p.window_end >= since]
        return sorted(points, key=lambda p: p.window_end)

    def anomalies_since(self, *, since: float) -> list[AnomalyEvent]:
        with self._lock:
            events = list(self._anomalies)
        return sorted((e for e in events if e.detected_at >= since), key=lambda e: e.detected_at)

    def has_seen_any_window_before(self, cutoff: float) -> bool:
        """True if the store has received at least one topic_p/topic_h
        window whose timestamp is <= cutoff — used to distinguish
        "genuinely zero anomalies" from "not enough history yet"
        (MODEL_COLD_START, 02-agents-and-tools.md C.2.4)."""
        with self._lock:
            return self._earliest_window_seen is not None and self._earliest_window_seen <= cutoff

    def all_device_ids(self) -> tuple[DeviceId, ...]:
        return ALL_DEVICE_IDS

    def freshness_summary(
        self, device_id: DeviceId, *, fresh_sec: int, stale_sec: int
    ) -> DeviceFreshnessSummary:
        now = self.now()
        worst: Freshness | None = None
        worst_age: float | None = None
        worst_reading: DeviceReading | None = None
        per_metric: list[tuple[Metric, DeviceReading | None, float | None, Freshness]] = []
        for metric in metrics_for(device_id):
            reading = self.latest(device_id, metric)
            age = (now - reading.observed_at) if reading else None
            freshness = classify(age, fresh_sec=fresh_sec, stale_sec=stale_sec)
            per_metric.append((metric, reading, age, freshness))
            if worst is None or RANK[freshness] > RANK[worst]:
                worst, worst_age, worst_reading = freshness, age, reading
        assert worst is not None  # every registered device has >=1 metric in DEVICE_METRICS
        return DeviceFreshnessSummary(device_id, worst, worst_age, worst_reading, per_metric)

    def now(self) -> float:
        """Seam for tests to freeze time; production just uses wall clock."""
        return time.time()

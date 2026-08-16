"""The 4 read tools of the Field IoT Agent (docs/agent-core/02-agents-and-tools.md
B.3, C.2.1–C.2.4) — the only agent allowed to touch raw sensor data. Every
other agent must go through `evidence_refs` these tools emit
(ADR-003-evidence-refs-only.md).

M1 scope (roadmap 1.4): plain Python functions, called directly by tests —
NOT yet wrapped as LLM tool-calling schemas. That wiring is M2's job once
Router/Coordinator exist. Each function returns the unified shape:
  success: {"ok": True, "markdown": "<table for the LLM>", ...structured fields}
  error:   {"ok": False, "error_code", "message", "retryable", "suggested_action"}
(the error shape is A.3's unified error contract).
"""
from __future__ import annotations

from agent_core.devices import (
    ALL_DEVICE_IDS,
    ZONE,
    DeviceId,
    Freshness,
    Metric,
    WindowType,
    metrics_for,
    unit_for,
)
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.state.freshness import clamp_age, classify, data_completeness
from agent_core.state.store import FarmStateStore
from agent_core.timeutil import to_iso

_METRIC_VALUES = {m.value for m in Metric}
_MAX_SERIES_SAMPLE_POINTS = 24


def _error(code: str, message: str, *, retryable: bool = False, suggested_action: str = "NONE") -> dict:
    return {
        "ok": False,
        "error_code": code,
        "message": message,
        "retryable": retryable,
        "suggested_action": suggested_action,
    }


def _fmt_value(value: float) -> str:
    return f"{value:g}"


def _fmt_age(age_seconds: float | None) -> str | int:
    clamped = clamp_age(age_seconds)
    return "—" if clamped is None else int(clamped)


def _render_table(headers: list[str], rows: list[dict]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(lines)


def _downsample(points: list, max_points: int) -> list:
    if len(points) <= max_points:
        return points
    step = (len(points) - 1) / (max_points - 1)
    seen_indices: list[int] = []
    for i in range(max_points):
        idx = round(i * step)
        if not seen_indices or seen_indices[-1] != idx:
            seen_indices.append(idx)
    return [points[i] for i in seen_indices]


# --- C.2.1 get_device_snapshot ------------------------------------------------


def get_device_snapshot(
    store: FarmStateStore, ledger: EvidenceLedger, settings, *, device_ids: list[str]
) -> dict:
    if device_ids:
        target_ids: list[DeviceId] = []
        for raw_id in device_ids:
            try:
                target_ids.append(DeviceId(raw_id))
            except ValueError:
                return _error("DEVICE_UNKNOWN", f'"{raw_id}" không phải device_id hợp lệ (enum 6 thiết bị).')
    else:
        target_ids = list(ALL_DEVICE_IDS)  # empty array = all 6 devices

    try:
        rows: list[dict] = []
        device_freshness: dict[DeviceId, Freshness] = {}
        for device_id in target_ids:
            summary = store.freshness_summary(
                device_id, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec
            )
            device_freshness[device_id] = summary.worst
            for metric, reading, age, freshness in summary.per_metric:
                unit = unit_for(device_id, metric)

                if reading is None or freshness == Freshness.OFFLINE:
                    # Poka-yoke (02-agents-and-tools.md A.2): never a bare
                    # null for a dead device — an explicit OFFLINE row with
                    # no evidence_id forces the LLM to see the absence.
                    rows.append(
                        {
                            "device_id": device_id.value,
                            "metric": metric.value,
                            "value": "—",
                            "unit": unit,
                            "age_seconds": _fmt_age(age),
                            "freshness": freshness.value,
                            "evidence_id": "—",
                        }
                    )
                    continue

                evidence = ledger.record(
                    device_id=device_id,
                    metric=metric.value,
                    value_text=_fmt_value(reading.value),
                    unit=unit,
                    observed_at=reading.observed_at,
                    age_seconds=age,
                    freshness=freshness,
                    source_topic=reading.source_topic,
                )
                rows.append(
                    {
                        "device_id": device_id.value,
                        "metric": metric.value,
                        "value": _fmt_value(reading.value),
                        "unit": unit,
                        "age_seconds": _fmt_age(age),
                        "freshness": freshness.value,
                        "evidence_id": evidence.evidence_id,
                    }
                )
    except Exception as exc:  # noqa: BLE001 — normalize any store failure to the unified error shape
        return _error("UPSTREAM_TIMEOUT", f"Farm State Store không phản hồi: {exc}", retryable=True)

    ratio, _mode = data_completeness(device_freshness)
    table = _render_table(
        ["device_id", "metric", "value", "unit", "age_seconds", "freshness", "evidence_id"], rows
    )
    summary = f"data_completeness: {ratio} thiết bị được yêu cầu đang FRESH"
    return {"ok": True, "markdown": f"{table}\n\n{summary}", "data_completeness": ratio, "rows": rows}


# --- C.2.2 get_metric_series ---------------------------------------------------


def get_metric_series(
    store: FarmStateStore,
    ledger: EvidenceLedger,
    settings,
    *,
    device_id: str,
    metric: str,
    lookback_minutes: int,
    window_type: str | None = None,
) -> dict:
    try:
        device = DeviceId(device_id)
    except ValueError:
        return _error("DEVICE_UNKNOWN", f'"{device_id}" không phải device_id hợp lệ.')

    try:
        metric_enum = Metric(metric)
    except ValueError:
        return _error("INVALID_ARGUMENT", f'"{metric}" không phải metric hợp lệ.')

    if metric_enum not in metrics_for(device):
        return _error("INVALID_ARGUMENT", f"{device.value} không phát ra chỉ số {metric_enum.value}.")

    if not (5 <= lookback_minutes <= 1440):
        return _error("INVALID_ARGUMENT", "lookback_minutes phải trong khoảng 5–1440.")

    # > 360 phút tự nâng lên HOURLY_1H (02-agents-and-tools.md C.2.2) —
    # a 1440-point TUMBLING_1M series would blow up the 3B model's context.
    effective_window_type = "HOURLY_1H" if lookback_minutes > 360 else (window_type or "TUMBLING_1M")

    now = store.now()
    try:
        points = store.series(device, metric_enum, window_type=effective_window_type, since=now - lookback_minutes * 60)
        latest_reading = store.latest(device, metric_enum)
    except Exception as exc:  # noqa: BLE001
        return _error("UPSTREAM_TIMEOUT", f"Farm State Store không phản hồi: {exc}", retryable=True)

    latest_age = (now - latest_reading.observed_at) if latest_reading else None
    latest_freshness = classify(
        latest_age, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec
    )
    if latest_freshness == Freshness.OFFLINE:
        return _error(
            "DEVICE_OFFLINE",
            f"{device.value} không có dữ liệu mới trong {_fmt_age(latest_age)} giây.",
            suggested_action="CREATE_INSPECTION_TICKET",
        )

    if len(points) < 3:
        return _error(
            "INSUFFICIENT_DATA",
            f"Chỉ có {len(points)} điểm dữ liệu cho {device.value}.{metric_enum.value}, cần ít nhất 3.",
        )

    sampled = _downsample(points, _MAX_SERIES_SAMPLE_POINTS)
    first, last = sampled[0], sampled[-1]
    hours_span = max((last.window_end - first.window_end) / 3600.0, 1e-9)
    trend_per_hour = (last.avg - first.avg) / hours_span
    series_min = min(p.min for p in sampled)
    series_max = max(p.max for p in sampled)

    unit = unit_for(device, metric_enum)
    source_topic = "topic_h" if effective_window_type == "HOURLY_1H" else "topic_p"
    window_type_enum = (
        WindowType(effective_window_type) if effective_window_type in WindowType._value2member_map_ else WindowType.NONE
    )
    last_age = now - last.window_end
    evidence = ledger.record(
        device_id=device,
        metric=metric_enum.value,
        value_text=f"{_fmt_value(first.avg)}→{_fmt_value(last.avg)}",
        unit=unit,
        observed_at=last.window_end,
        age_seconds=last_age,
        freshness=classify(last_age, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec),
        source_topic=source_topic,
        window_type=window_type_enum,
    )

    rows = [
        {
            "window_end_iso": to_iso(p.window_end),
            "avg": _fmt_value(p.avg),
            "min": _fmt_value(p.min),
            "max": _fmt_value(p.max),
        }
        for p in sampled
    ]
    table = _render_table(["window_end_iso", "avg", "min", "max"], rows)
    summary = (
        f"first: {_fmt_value(first.avg)}{unit} | last: {_fmt_value(last.avg)}{unit} | "
        f"min: {_fmt_value(series_min)}{unit} | max: {_fmt_value(series_max)}{unit} | "
        f"trend_per_hour: {trend_per_hour:+.2f}{unit}/h | evidence_id: {evidence.evidence_id}"
    )
    return {
        "ok": True,
        "markdown": f"{table}\n\n{summary}",
        "first": first.avg,
        "last": last.avg,
        "min": series_min,
        "max": series_max,
        "trend_per_hour": trend_per_hour,
        "evidence_id": evidence.evidence_id,
    }


# --- C.2.3 get_freshness_report -------------------------------------------------


def get_freshness_report(store: FarmStateStore, ledger: EvidenceLedger, settings) -> dict:
    now = store.now()
    try:
        fresh: list[str] = []
        stale: list[dict] = []
        offline: list[dict] = []
        device_freshness: dict[DeviceId, Freshness] = {}

        for device_id in store.all_device_ids():
            summary = store.freshness_summary(
                device_id, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec
            )
            device_freshness[device_id] = summary.worst

            if summary.worst == Freshness.FRESH:
                fresh.append(device_id.value)
            elif summary.worst == Freshness.STALE:
                stale.append({"device_id": device_id.value, "age_seconds": _fmt_age(summary.worst_age)})
            else:
                last_seen_iso = to_iso(summary.worst_reading.observed_at) if summary.worst_reading else None
                representative_metric = (
                    summary.worst_reading.metric if summary.worst_reading else next(iter(metrics_for(device_id)))
                )
                ledger.record(
                    device_id=device_id,
                    metric=representative_metric.value,
                    value_text="—",
                    unit=unit_for(device_id, representative_metric),
                    observed_at=summary.worst_reading.observed_at if summary.worst_reading else now,
                    age_seconds=summary.worst_age if summary.worst_age is not None else -1.0,
                    freshness=Freshness.OFFLINE,
                    source_topic="topic_raw",
                    is_absence_record=True,
                )
                offline.append(
                    {
                        "device_id": device_id.value,
                        "age_seconds": _fmt_age(summary.worst_age),
                        "last_seen_iso": last_seen_iso,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        return _error("UPSTREAM_TIMEOUT", f"Farm State Store không phản hồi: {exc}", retryable=True)

    ratio, mode = data_completeness(device_freshness)
    rows = (
        [{"device_id": d, "status": "FRESH", "age_seconds": "—", "last_seen_iso": "—"} for d in fresh]
        + [
            {"device_id": s["device_id"], "status": "STALE", "age_seconds": s["age_seconds"], "last_seen_iso": "—"}
            for s in stale
        ]
        + [
            {
                "device_id": o["device_id"],
                "status": "OFFLINE",
                "age_seconds": o["age_seconds"],
                "last_seen_iso": o["last_seen_iso"] or "—",
            }
            for o in offline
        ]
    )
    table = _render_table(["device_id", "status", "age_seconds", "last_seen_iso"], rows)
    summary = f"data_completeness: {ratio} | mode: {mode}"
    return {
        "ok": True,
        "markdown": f"{table}\n\n{summary}",
        "fresh": fresh,
        "stale": stale,
        "offline": offline,
        "data_completeness": ratio,
        "mode": mode,
    }


# --- C.2.4 get_anomaly_report ---------------------------------------------------


def get_anomaly_report(
    store: FarmStateStore, ledger: EvidenceLedger, settings, *, zone: str, lookback_minutes: int = 60
) -> dict:
    if zone != ZONE:
        return _error("INVALID_ARGUMENT", f'"{zone}" không phải zone hợp lệ (chỉ có {ZONE}).')
    if not (10 <= lookback_minutes <= 720):
        return _error("INVALID_ARGUMENT", "lookback_minutes phải trong khoảng 10–720.")

    now = store.now()
    cutoff = now - lookback_minutes * 60
    try:
        has_history = store.has_seen_any_window_before(cutoff)
    except Exception as exc:  # noqa: BLE001
        return _error("UPSTREAM_TIMEOUT", f"Farm State Store không phản hồi: {exc}", retryable=True)

    if not has_history:
        # "Chưa biết" != "không có gì bất thường" (C.2.4) — normal in the
        # first ~10 minutes after the service starts, not an error to hide.
        return _error(
            "MODEL_COLD_START",
            f"Chưa đủ lịch sử {lookback_minutes} phút để kết luận — hệ thống vừa khởi động.",
            retryable=True,
            suggested_action="RETRY_LATER",
        )

    events = store.anomalies_since(since=cutoff)
    anomalies = []
    for event in events:
        score = 0.9 if event.severity == "HIGH" else 0.5
        unit = unit_for(event.device_id, Metric(event.metric)) if event.metric in _METRIC_VALUES else ""
        age = now - event.detected_at
        evidence = ledger.record(
            device_id=event.device_id,
            metric=event.metric,
            value_text=_fmt_value(event.value),
            unit=unit,
            observed_at=event.detected_at,
            age_seconds=age,
            freshness=classify(age, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec),
            source_topic="topic_p",
        )
        anomalies.append(
            {
                "anomaly_type": event.anomaly_type,
                "device_id": event.device_id.value,
                # Rule-based severity from the stream layer (aggregators.py),
                # NOT an ML model — see M1 plan design decision #5. Real ML
                # anomaly detection is M3 (05-ml-interfaces.md).
                "score_0_1": score,
                "detected_at_iso": to_iso(event.detected_at),
                "model_version": "stream-rules-v1",
                "evidence_refs": [evidence.evidence_id],
            }
        )

    if anomalies:
        rows = [
            {
                "anomaly_type": a["anomaly_type"],
                "device_id": a["device_id"],
                "score_0_1": a["score_0_1"],
                "detected_at_iso": a["detected_at_iso"],
                "evidence_id": a["evidence_refs"][0],
            }
            for a in anomalies
        ]
        markdown = _render_table(["anomaly_type", "device_id", "score_0_1", "detected_at_iso", "evidence_id"], rows)
    else:
        markdown = f"(Không có bất thường nào trong {lookback_minutes} phút gần nhất)"

    return {"ok": True, "markdown": markdown, "anomalies": anomalies}


# --- M2: LLM Tool Schema Wrappers -------------------------------------------


def to_llm_tool_schemas() -> list[dict]:
    """Convert the 4 Field IoT tools to OpenAI function calling format.

    Follows Schema Intersection Rule (03-contracts.md §1):
    - No $ref, no anyOf, flat structure
    - Enum for device_id (6 values), metric, window_type
    - additionalProperties: false
    """
    device_id_enum = [d.value for d in ALL_DEVICE_IDS]
    metric_enum = [m.value for m in Metric]
    window_type_enum = [w.value for w in WindowType if w != WindowType.NONE]

    return [
        {
            "type": "function",
            "function": {
                "name": "get_device_snapshot",
                "description": "Lấy snapshot hiện tại của các thiết bị (giá trị mới nhất, độ tươi dữ liệu)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_ids": {
                            "type": "array",
                            "items": {"type": "string", "enum": device_id_enum},
                            "description": "Danh sách device_id cần tra (rỗng = tất cả 6 thiết bị)",
                        }
                    },
                    "required": ["device_ids"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_metric_series",
                "description": "Lấy chuỗi thời gian của một metric (dữ liệu gom cửa sổ)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "enum": device_id_enum, "description": "Device_id cần tra"},
                        "metric": {"type": "string", "enum": metric_enum, "description": "Metric cần tra"},
                        "lookback_minutes": {
                            "type": "integer",
                            "description": "Khoảng thời gian nhìn lại (phút)",
                            "minimum": 1,
                            "maximum": 1440,
                        },
                        "window_type": {
                            "type": "string",
                            "enum": window_type_enum,
                            "description": "Loại cửa sổ gom",
                        },
                    },
                    "required": ["device_id", "metric", "lookback_minutes", "window_type"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_freshness_report",
                "description": "Lấy báo cáo độ tươi dữ liệu toàn bộ 6 thiết bị (FRESH/STALE/OFFLINE)",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_anomaly_report",
                "description": "Lấy danh sách bất thường phát hiện trong khoảng thời gian gần đây",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zone": {"type": "string", "description": "Tên khu vực (ví dụ: ZONE_A)"},
                        "lookback_minutes": {
                            "type": "integer",
                            "description": "Khoảng thời gian nhìn lại (phút)",
                            "minimum": 1,
                            "maximum": 1440,
                        },
                    },
                    "required": ["zone", "lookback_minutes"],
                    "additionalProperties": False,
                },
            },
        },
    ]

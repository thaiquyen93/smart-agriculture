import math
from typing import List, Dict, Any

def aggregate_window_records(records: List[Dict[str, Any]], window_type: str, window_start: float, window_end: float) -> Dict[str, Any]:
    """
    Domain-Agnostic Universal Telemetry Aggregator.
    Automatically computes avg, min, max, trend for ANY numerical metrics in JSON payload.
    Supports weather, traffic, factory IoT, energy grid, smart city, etc.
    """
    if not records:
        return {}

    first = records[0]
    device_id = first.get("device_id") or first.get("station_id") or "DEV_UNKNOWN"
    device_name = first.get("device_name") or first.get("station_name") or device_id
    region = first.get("region") or first.get("zone") or "Default"
    lat = first.get("lat", 0.0)
    lon = first.get("lon", 0.0)

    # Collect all numeric fields dynamically across all records
    numeric_keys = set()
    for r in records:
        for k, v in r.items():
            if isinstance(v, (int, float)) and k not in ("event_time", "created_at", "ingestion_time", "lat", "lon"):
                numeric_keys.add(k)

    computed_metrics: Dict[str, Any] = {}
    for key in numeric_keys:
        values = [r[key] for r in records if key in r and isinstance(r[key], (int, float))]
        if values:
            avg_val = sum(values) / len(values)
            min_val = min(values)
            max_val = max(values)
            trend_val = round(values[-1] - values[0], 2) if len(values) >= 2 else 0.0
            
            computed_metrics[f"{key}_avg"] = round(avg_val, 2)
            computed_metrics[f"{key}_min"] = round(min_val, 2)
            computed_metrics[f"{key}_max"] = round(max_val, 2)
            computed_metrics[f"{key}_trend"] = trend_val

    return {
        "device_id": device_id,
        "station_id": device_id,  # Alias
        "device_name": device_name,
        "region": region,
        "lat": lat,
        "lon": lon,
        "window_type": window_type, # TUMBLING_1M, SLIDING_5M, HOURLY_1H
        "window_start": window_start,
        "window_end": window_end,
        "window_duration_sec": round(window_end - window_start, 2),
        "record_count": len(records),
        "metrics": computed_metrics,
        "created_at": window_end
    }

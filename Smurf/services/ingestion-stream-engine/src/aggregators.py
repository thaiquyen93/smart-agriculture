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

    # Detect anomalies for Track B Smart Agriculture metrics
    anomalies: List[Dict[str, Any]] = []

    soil_avg = computed_metrics.get("soil_moisture_avg")
    if soil_avg is not None:
        if soil_avg < 35.0:
            anomalies.append({
                "type": "SOIL_MOISTURE_CRITICAL_LOW",
                "severity": "HIGH",
                "metric": "soil_moisture",
                "val": soil_avg,
                "msg": f"CẢNH BÁO: Độ ẩm đất quá thấp ({soil_avg}% < 35%). Cần kích hoạt tưới khẩn cấp!"
            })
        elif soil_avg > 90.0:
            anomalies.append({
                "type": "SOIL_MOISTURE_SATURATED",
                "severity": "WARNING",
                "metric": "soil_moisture",
                "val": soil_avg,
                "msg": f"CẢNH BÁO: Đất quá úng nước ({soil_avg}% > 90%)."
            })

    temp_avg = computed_metrics.get("temperature_avg")
    if temp_avg is not None and temp_avg > 42.0:
        anomalies.append({
            "type": "EXTREME_HEAT_ALERT",
            "severity": "HIGH",
            "metric": "temperature",
            "val": temp_avg,
            "msg": f"CẢNH BÁO: Nhiệt độ môi trường cực cao ({temp_avg}°C > 42°C)."
        })

    tank_level = computed_metrics.get("level_avg")
    if tank_level is not None and tank_level < 20.0:
        anomalies.append({
            "type": "TANK_WATER_DEFICIT",
            "severity": "HIGH",
            "metric": "level",
            "val": tank_level,
            "msg": f"CẢNH BÁO: Mực nước bồn TANK_01 sắp cạn ({tank_level}% < 20%)."
        })

    ph_avg = computed_metrics.get("ph_avg")
    if ph_avg is not None and (ph_avg < 5.5 or ph_avg > 8.5):
        anomalies.append({
            "type": "PH_IMBALANCE",
            "severity": "WARNING",
            "metric": "ph",
            "val": ph_avg,
            "msg": f"CẢNH BÁO: Độ pH nước bất thường ({ph_avg} pH)."
        })

    return {
        "device_id": device_id,
        "station_id": device_id,  # Alias
        "device_name": device_name,
        "region": region,
        "lat": lat,
        "lon": lon,
        "window_type": window_type, # TUMBLING_1M, SLIDING_10M, HOURLY_1H
        "window_start": window_start,
        "window_end": window_end,
        "window_duration_sec": round(window_end - window_start, 2),
        "record_count": len(records),
        "metrics": computed_metrics,
        "anomalies": anomalies,
        "created_at": window_end
    }

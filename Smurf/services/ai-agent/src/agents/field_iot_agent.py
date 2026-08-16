import time
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("field_iot_agent")

class FieldIoTAgent:
    """
    1. Field IoT Agent
    Reads telemetry from 6 sensors (SOIL_01, WEATHER_01, PUMP_01, PH_01, TANK_01, SUN_01).
    Validates data freshness and enforces Partial Data Mode when sensors go offline.
    Crucial Rule: NEVER hallucinate or invent fake sensor values when data is stale.
    """
    def __init__(self, stale_threshold_sec: float = 30.0):
        self.stale_threshold_sec = stale_threshold_sec
        self.required_devices = ["SOIL_01", "WEATHER_01", "PUMP_01", "PH_01", "TANK_01", "SUN_01"]

    def analyze_sensor_states(self, device_states: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        current_time = time.time()
        active_devices = []
        stale_devices = []
        missing_devices = []

        valid_metrics = {}

        for dev in self.required_devices:
            if dev not in device_states or not device_states[dev]:
                missing_devices.append(dev)
                continue

            state = device_states[dev]
            created_at = state.get("created_at") or state.get("timestamp") or current_time
            age_sec = current_time - created_at

            if age_sec > self.stale_threshold_sec:
                stale_devices.append((dev, round(age_sec, 1)))
            else:
                active_devices.append(dev)
                payload = state.get("payload", {})
                valid_metrics[dev] = payload

        # Check if running in Partial Mode
        is_partial_mode = len(stale_devices) > 0 or len(missing_devices) > 0
        active_ratio = f"{len(active_devices)}/{len(self.required_devices)}"

        logger.info(f"📡 [FieldIoTAgent] Active Sensors: {active_ratio} | Partial Mode: {is_partial_mode}")

        return {
            "agent_name": "FieldIoTAgent",
            "active_ratio": active_ratio,
            "is_partial_mode": is_partial_mode,
            "active_devices": active_devices,
            "stale_devices": stale_devices,
            "missing_devices": missing_devices,
            "metrics": valid_metrics,
            "evidence": {
                "soil_moisture": valid_metrics.get("SOIL_01", {}).get("soil_moisture"),
                "air_temp": valid_metrics.get("WEATHER_01", {}).get("temperature"),
                "air_humidity": valid_metrics.get("WEATHER_01", {}).get("humidity"),
                "pump_status": valid_metrics.get("PUMP_01", {}).get("status", "UNKNOWN"),
                "ph": valid_metrics.get("PH_01", {}).get("ph"),
                "tank_level": valid_metrics.get("TANK_01", {}).get("level"),
                "sun_lux": valid_metrics.get("SUN_01", {}).get("lux")
            }
        }

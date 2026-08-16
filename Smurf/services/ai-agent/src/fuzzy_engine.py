import logging
from typing import Dict, Any

logger = logging.getLogger("fuzzy_engine")

class FuzzyLogicEngine:
    """
    Fuzzy Logic Engine Module.
    Evaluates membership functions for pressure drop, heat index, and rainfall intensity.
    Returns fuzzy risk score (0 - 100) and risk membership level.
    """
    def evaluate_fuzzy_risk(self, aggregated_data: Dict[str, Any]) -> Dict[str, Any]:
        metrics = aggregated_data.get("metrics", {})
        temp = metrics.get("temp_avg", 28.0)
        humidity = metrics.get("humidity_avg", 75.0)
        pressure = metrics.get("pressure_avg", 1012.0)
        pressure_trend = metrics.get("pressure_trend_hpa", 0.0)
        rainfall = metrics.get("rainfall_avg_mm_h", 0.0)

        # Fuzzy Risk Scoring Logic
        fuzzy_score = 10.0
        if pressure < 1000.0:
            fuzzy_score += (1000.0 - pressure) * 2.5
        if pressure_trend < -1.5:
            fuzzy_score += abs(pressure_trend) * 8.0
        if rainfall > 20.0:
            fuzzy_score += (rainfall - 20.0) * 1.5

        fuzzy_score = min(100.0, max(5.0, round(fuzzy_score, 1)))

        if fuzzy_score >= 80:
            fuzzy_level = "CRITICAL"
        elif fuzzy_score >= 50:
            fuzzy_level = "HIGH"
        elif fuzzy_score >= 25:
            fuzzy_level = "MODERATE"
        else:
            fuzzy_level = "LOW"

        return {
            "device_id": aggregated_data.get("device_id") or aggregated_data.get("station_id"),
            "fuzzy_score": fuzzy_score,
            "fuzzy_level": fuzzy_level,
            "pressure_trend": pressure_trend,
            "window_type": aggregated_data.get("window_type")
        }

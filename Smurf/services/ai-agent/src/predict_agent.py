import logging
import time
from typing import Dict, Any

logger = logging.getLogger("predict_agent")

class PredictAgent:
    """
    Time-Series Predict Agent Module.
    Predicts future trend projection over 1-hour and 6-hour horizons.
    """
    def predict_future_trend(self, aggregated_data: Dict[str, Any], fuzzy_result: Dict[str, Any]) -> Dict[str, Any]:
        metrics = aggregated_data.get("metrics", {})
        temp = metrics.get("temp_avg", 28.0)
        pressure_trend = metrics.get("pressure_trend_hpa", 0.0)
        fuzzy_level = fuzzy_result.get("fuzzy_level", "LOW")

        if fuzzy_level in ("HIGH", "CRITICAL") or pressure_trend <= -2.0:
            pred_6h = "Gió mạnh và mưa lớn có khả năng dồn dập, nguy cơ ngập úng vùng trũng thấp."
            pred_24h = "Bão/áp thấp nhiệt đới đi sâu vào đất liền trước khi suy yếu dần."
            predicted_risk = "HIGH_STORM_RISK"
        else:
            pred_6h = "Nền nhiệt duy trì ổn định, thời tiết thuận lợi cho hoạt động ngoài trời."
            pred_24h = "Xu thế thời tiết chung không có biến động bất thường."
            predicted_risk = "STABLE"

        return {
            "device_id": aggregated_data.get("device_id") or aggregated_data.get("station_id"),
            "predicted_risk": predicted_risk,
            "forecast_horizons": {
                "6_hours": pred_6h,
                "24_hours": pred_24h
            },
            "timestamp": time.time()
        }

import logging
from typing import Dict, Any, List

logger = logging.getLogger("inference_engine")

class OperationalInferenceEngine:
    """
    Operational Decision Inference Engine.
    Combines raw telemetry, fuzzy results, and predict results to output:
    - Anomalies
    - Root Causes
    - Smart Operational Action Decisions
    """
    def evaluate_inference(self, raw_data: Dict[str, Any], fuzzy_result: Dict[str, Any], predict_result: Dict[str, Any]) -> Dict[str, Any]:
        fuzzy_score = fuzzy_result.get("fuzzy_score", 10.0)
        fuzzy_level = fuzzy_result.get("fuzzy_level", "LOW")
        
        anomalies = []
        root_causes = []
        decisions = []

        if fuzzy_score >= 80:
            anomalies.append("CRITICAL_PRESSURE_DROP_STORM")
            root_causes.append("Khí áp sụt giảm đột ngột dưới 1000 hPa kèm xu hướng dốc")
            decisions.append("KÍCH HOẠT HỆ THỐNG BƠM XẢ LŨ CÔNG SUẤT LỚN")
            decisions.append("PHÁT THÔNG BÁO KHẨN CẤP ĐẾN BAN CHỈ ĐẠO THIÊN TAI")
        elif fuzzy_score >= 50:
            anomalies.append("MODERATE_WEATHER_DISTURBANCE")
            root_causes.append("Độ ẩm không khí tăng cao và biến động áp suất")
            decisions.append("TĂNG CƯỜNG GIÁM SÁT TRẠM QUAN TRẮC THỜI GIAN THỰC")
        else:
            decisions.append("DUY TRÌ VẬN HÀNH BÌNH THƯỜNG")

        return {
            "device_id": raw_data.get("device_id") or raw_data.get("station_id"),
            "fuzzy_level": fuzzy_level,
            "anomalies": anomalies,
            "root_causes": root_causes,
            "smart_decisions": decisions
        }

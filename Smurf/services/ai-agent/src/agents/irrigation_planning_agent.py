import logging
from typing import Dict, Any

logger = logging.getLogger("irrigation_agent")

class IrrigationPlanningAgent:
    """
    2. Irrigation Planning Agent
    Analyzes soil moisture (SOIL_01), weather (WEATHER_01), and sunlight (SUN_01).
    Proposes optimal irrigation water volume (Liters), priority, and schedule.
    """
    def __init__(self, target_moisture_pct: float = 65.0):
        self.target_moisture_pct = target_moisture_pct

    def create_irrigation_plan(self, iot_analysis: Dict[str, Any], area_id: str = "Khu A") -> Dict[str, Any]:
        metrics = iot_analysis.get("metrics", {})
        evidence = iot_analysis.get("evidence", {})

        soil_moisture = evidence.get("soil_moisture")
        air_temp = evidence.get("air_temp", 28.0)
        sun_lux = evidence.get("sun_lux", 30000.0)

        # Handle Partial Data Mode when soil moisture sensor is offline
        if soil_moisture is None:
            logger.warning("⚠️ [IrrigationPlanningAgent] SOIL_01 sensor offline! Cannot calculate exact moisture deficit.")
            return {
                "agent_name": "IrrigationPlanningAgent",
                "can_proceed": False,
                "reason": "Cảm biến SOIL_01 bị ngắt kết nối. Hệ thống chuyển sang Partial Mode và cần kỹ sư kiểm tra thiết bị.",
                "recommended_action": "CREATE_INSPECTION_TASK"
            }

        # Calculate moisture deficit
        deficit = self.target_moisture_pct - soil_moisture

        if deficit <= 0:
            return {
                "agent_name": "IrrigationPlanningAgent",
                "can_proceed": True,
                "need_irrigation": False,
                "reason": f"Độ ẩm đất hiện tại là {soil_moisture}% đã đạt ngưỡng tối ưu (>= {self.target_moisture_pct}%). Không cần tưới.",
                "water_amount_liters": 0.0,
                "priority": "LOW"
            }

        # Calculate water volume: 1% deficit = 15 Liters per 100m2
        water_amount = round(deficit * 15.0, 1)

        # Determine priority
        if soil_moisture < 35.0:
            priority = "HIGH"
            suggested_time = "Tưới ngay lập tức"
        elif soil_moisture < 50.0:
            priority = "MEDIUM"
            suggested_time = "Tưới vào 16:30 Chiều"
        else:
            priority = "LOW"
            suggested_time = "Tưới vào 18:00 Tối"

        summary = (
            f"Độ ẩm đất {soil_moisture}% (Thiếu {deficit:.1f}%). "
            f"Nhiệt độ kk {air_temp}°C, Nắng {sun_lux:.0f} lux. "
            f"Đề xuất tưới {water_amount} Liters cho {area_id} ({suggested_time})."
        )

        logger.info(f"💧 [IrrigationPlanningAgent] Plan generated: {water_amount}L | Priority: {priority}")

        return {
            "agent_name": "IrrigationPlanningAgent",
            "can_proceed": True,
            "need_irrigation": True,
            "area_id": area_id,
            "soil_moisture_current": soil_moisture,
            "target_moisture": self.target_moisture_pct,
            "water_amount_liters": water_amount,
            "priority": priority,
            "suggested_time": suggested_time,
            "reasoning_summary": summary
        }

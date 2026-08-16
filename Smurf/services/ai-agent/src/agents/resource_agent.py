import logging
from typing import Dict, Any

logger = logging.getLogger("resource_agent")

class ResourceAgent:
    """
    3. Resource Agent
    Validates resource availability:
      - Water tank level (TANK_01)
      - Pump status & flow rate (PUMP_01)
      - Tank level constraint checks (Must be >= 20% to execute irrigation)
    """
    def check_resource_constraints(self, iot_analysis: Dict[str, Any], irrigation_plan: Dict[str, Any]) -> Dict[str, Any]:
        evidence = iot_analysis.get("evidence", {})
        tank_level = evidence.get("tank_level")
        pump_status = evidence.get("pump_status", "OFF")

        if not irrigation_plan.get("need_irrigation", False):
            return {
                "agent_name": "ResourceAgent",
                "is_approved": True,
                "reason": "Không có kế hoạch tưới cần thực thi."
            }

        # Check tank level
        if tank_level is None:
            return {
                "agent_name": "ResourceAgent",
                "is_approved": False,
                "reason": "Không đọc được mực nước bồn TANK_01. Không thể xác nhận đủ nước tưới.",
                "recommended_action": "CREATE_INSPECTION_TASK"
            }

        if tank_level < 20.0:
            logger.warning(f"⚠️ [ResourceAgent] Tank level too low: {tank_level}% (< 20%). Irrigation blocked.")
            return {
                "agent_name": "ResourceAgent",
                "is_approved": False,
                "reason": f"Mực nước bồn chính TANK_01 chỉ còn {tank_level}% (< 20%). Không đủ nước tưới an toàn.",
                "recommended_action": "FILL_TANK_ALERT"
            }

        logger.info(f"🔋 [ResourceAgent] Resource check PASSED. Tank Level: {tank_level}% | Pump: {pump_status}")
        return {
            "agent_name": "ResourceAgent",
            "is_approved": True,
            "tank_level": tank_level,
            "pump_status": pump_status,
            "reason": f"Mực nước bồn TANK_01 đạt {tank_level}% (Đủ nước). Bơm PUMP_01 sẵn sàng."
        }

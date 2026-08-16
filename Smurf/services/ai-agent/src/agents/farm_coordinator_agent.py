import logging
import time
from typing import Dict, Any, List
from src.agents.field_iot_agent import FieldIoTAgent
from src.agents.irrigation_planning_agent import IrrigationPlanningAgent
from src.agents.resource_agent import ResourceAgent
from src.agents.farm_action_agent import FarmActionAgent

logger = logging.getLogger("farm_coordinator_agent")

class FarmCoordinatorAgent:
    """
    5. Farm Coordinator Agent (Master Agent)
    Orchestrates the 4 sub-agents for Track B scenarios:
      - Scenario 1: Plan daily irrigation for Area A
      - Scenario 2: Inspect active irrigation & pump performance
      - Scenario 3: Handle sensor disruptions / partial data mode
    Provides clear reasoning trace and submits plan for Human Manager Approval.
    """
    def __init__(self, producer=None):
        self.iot_agent = FieldIoTAgent()
        self.irrigation_agent = IrrigationPlanningAgent()
        self.resource_agent = ResourceAgent()
        self.action_agent = FarmActionAgent()
        self.producer = producer

    def process_manager_request(self, user_prompt: str, device_states: Dict[str, Dict[str, Any]], 
                                session_id: str = None) -> Dict[str, Any]:
        session_id = session_id or f"SESS-{int(time.time())}"
        logger.info(f"👑 [FarmCoordinatorAgent] Processing request: '{user_prompt}' (Session: {session_id})")

        reasoning_trace = []

        # Step 1: Assign Field IoT Agent to read 6 sensors
        iot_result = self.iot_agent.analyze_sensor_states(device_states)
        reasoning_trace.append({
            "step": 1,
            "agent": "FieldIoTAgent",
            "action": "Đọc dữ liệu 6 cảm biến & kiểm tra độ tươi dữ liệu",
            "active_sensors": iot_result["active_ratio"],
            "is_partial_mode": iot_result["is_partial_mode"],
            "evidence": iot_result["evidence"]
        })

        # Scenario 3: Sensor Disruption Handling
        if iot_result["is_partial_mode"]:
            missing_or_stale = iot_result["stale_devices"] + iot_result["missing_devices"]
            desc = f"Phát hiện thiết bị bị ngắt kết nối/dữ liệu cũ: {missing_or_stale}. Chuyển sang Partial Mode."
            
            # Action Agent creates inspection task for offline sensors
            task_result = self.action_agent.execute_create_task_tool(
                device_id=str(missing_or_stale[0][0]) if stale_devices_exist(iot_result) else "DEV_OFFLINE",
                issue_type="SENSOR_DISRUPTION",
                description=f"Nhiệm vụ kiểm tra cảm biến bị gián đoạn: {desc}",
                severity="CRITICAL",
                producer=self.producer
            )

            reasoning_trace.append({
                "step": 2,
                "agent": "FarmActionAgent",
                "action": "Tạo phiếu kiểm tra thiết bị gián đoạn (Scenario 3)",
                "task_created": task_result["task_id"],
                "verification": task_result["verification"]
            })

        # Step 2: Assign Irrigation Planning Agent
        irrigation_result = self.irrigation_agent.create_irrigation_plan(iot_result, area_id="Khu A - Nông trường Rau Củ")
        reasoning_trace.append({
            "step": 3,
            "agent": "IrrigationPlanningAgent",
            "action": "Tính toán độ ẩm mục tiêu & lượng nước tưới",
            "plan_output": irrigation_result
        })

        # Step 3: Assign Resource Agent to check water tank & pump
        resource_result = self.resource_agent.check_resource_constraints(iot_result, irrigation_result)
        reasoning_trace.append({
            "step": 4,
            "agent": "ResourceAgent",
            "action": "Kiểm tra ràng buộc mực nước bồn TANK_01 & Bơm PUMP_01",
            "resource_check": resource_result
        })

        # Step 4: Final Synthesis & Action Execution
        action_output = None
        final_summary = ""

        if irrigation_result.get("need_irrigation", False) and resource_result.get("is_approved", False):
            # Create irrigation plan and request human approval
            action_output = self.action_agent.execute_create_plan_tool(
                plan_data=irrigation_result,
                producer=self.producer
            )
            final_summary = (
                f"✅ KẾ HOẠCH TƯỚI ĐÃ ĐƯỢC LẬP (Chờ Người Quản Lý Phê Duyệt).\n"
                f"• Khu vực: Khu A - Nông trường Rau Củ\n"
                f"• Lượng nước đề xuất: {irrigation_result['water_amount_liters']} Liters ({irrigation_result['suggested_time']})\n"
                f"• Căn cứ dữ liệu: Độ ẩm đất {iot_result['evidence']['soil_moisture']}%, Mực nước bồn {resource_result['tank_level']}%\n"
                f"• Mã kế hoạch: {action_output['plan_id']}"
            )
            reasoning_trace.append({
                "step": 5,
                "agent": "FarmActionAgent",
                "action": "Tạo Kế Hoạch Tưới & Yêu Cầu Phê Duyệt (Human Approval)",
                "plan_id": action_output['plan_id'],
                "verification": action_output['verification']
            })
        elif not irrigation_result.get("need_irrigation", False):
            final_summary = f"ℹ️ Không cần tưới. {irrigation_result.get('reason', '')}"
        else:
            final_summary = f"⚠️ Không thể thực thi tưới. Lý do: {resource_result.get('reason', '')}"

        return {
            "session_id": session_id,
            "user_prompt": user_prompt,
            "final_summary": final_summary,
            "reasoning_trace": reasoning_trace,
            "action_output": action_output,
            "status": "COMPLETED"
        }

def stale_devices_exist(iot_result):
    return len(iot_result.get("stale_devices", [])) > 0 or len(iot_result.get("missing_devices", [])) > 0

import logging
from typing import Dict, Any, List
from app.agents.base import BaseAgent
from app.agents.agents import ValidationAgent, SynthesisAgent
from app.agents.fuzzy_agent import FuzzyAgent
from app.agents.predictive_agent import TorchPredictiveAgent
from app.agents.reasoning_agent import ReasoningAgent

logger = logging.getLogger(__name__)

class MultiAgentOrchestrator:
    """
    Orchestrator quản lý và thực thi luồng các BaseAgent.
    Cho phép cấu hình linh hoạt các tác vụ tuần tự.
    """
    def __init__(self):
        # Đăng ký các agent vào pipeline
        self.validation_agent = ValidationAgent()
        self.predictive_agent = TorchPredictiveAgent()
        self.fuzzy_agent = FuzzyAgent()
        self.reasoning_agent = ReasoningAgent()
        self.synthesis_agent = SynthesisAgent()
        
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[MultiAgent Flow] Bắt đầu xử lý với dữ liệu: {input_data}")
        
        # 1. Pipeline Validation
        step1_data = self.validation_agent.process(input_data)
        
        # 2. Pipeline Predictive (Torch)
        step2_data = self.predictive_agent.process(step1_data)
        
        # 3. Pipeline Inference (Fuzzy DB)
        step3_data = self.fuzzy_agent.process(step2_data)
        
        # 4. Pipeline Reasoning (Đánh giá sự hợp lý)
        step4_data = self.reasoning_agent.process(step3_data)
        
        # 5. Pipeline Synthesis (Đóng gói kết quả đầu ra)
        final_output = self.synthesis_agent.process(step4_data)
        
        logger.info(f"[MultiAgent Flow] Kết thúc xử lý: {final_output}")
        return final_output

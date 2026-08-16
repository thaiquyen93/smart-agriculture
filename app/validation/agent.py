from typing import Dict, Any
from app.core.base_agent import BaseAgent

class ValidationAgent(BaseAgent):
    """
    Agent chuyên trách việc kiểm tra và tiền xử lý dữ liệu.
    """
    
    def __init__(self):
        super().__init__(name="ValidationAgent")
        
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info(f"Đang kiểm tra dữ liệu: {data}")
        # Giả lập logic kiểm tra
        processed_data = data.copy()
        if 'value' not in processed_data:
            processed_data['value'] = 0
            
        if 'quality' not in processed_data:
            processed_data['quality'] = 5
            
        if 'service' not in processed_data:
            processed_data['service'] = 5
            
        return processed_data

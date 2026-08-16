from typing import Dict, Any
from app.agents.base import BaseAgent

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

class SynthesisAgent(BaseAgent):
    """
    Agent chuyên trách việc tổng hợp dữ liệu sau khi các model/agent khác đã xử lý.
    """
    
    def __init__(self):
        super().__init__(name="SynthesisAgent")
        
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info("Đang đóng gói dữ liệu kết quả chuẩn")
        
        # Chỉ trích xuất 4 trường quan trọng như yêu cầu
        return {
            "quyết định": data.get("quyết định", "Không có quyết định"),
            "nguyên nhân quyết định": data.get("nguyên nhân quyết định", "Không rõ nguyên nhân"),
            "bất thường": data.get("bất thường", False),
            "nguyên nhân bất thường": data.get("nguyên nhân bất thường", None)
        }

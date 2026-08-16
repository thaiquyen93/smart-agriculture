from typing import Dict, Any
from app.agents.base import BaseAgent

class ReasoningAgent(BaseAgent):
    """
    Agent sử dụng LLM để đánh giá tính hợp lý của "nguyên nhân quyết định" do Fuzzy Engine đưa ra.
    """
    def __init__(self):
        super().__init__(name="ReasoningAgent")
        
    def _call_llm_api(self, prompt: str) -> str:
        """
        Hàm gọi API của LLM (OpenAI/Gemini/...).
        Hiện tại đang giả lập trả về kết quả cứng.
        """
        # TODO: Thay thế bằng code gọi request tới LLM API thực tế
        if "tệ" in prompt.lower() or "thấp" in prompt.lower():
            return "FALSE" # Không hợp lý
        return "TRUE" # Hợp lý

    def propose_new_rule(self, original_data: Dict[str, Any], fuzzy_reason: str) -> str:
        """
        Dùng Agent để đề xuất một quy luật mới nếu hệ thống phát hiện bất thường.
        """
        prompt = f"Hệ thống đã ra nguyên nhân: '{fuzzy_reason}' với dữ liệu: {original_data}. Điều này là bất hợp lý. Hãy đề xuất một luật (rule) mờ mới để sửa sai."
        # TODO: Gọi LLM
        return f"Đề xuất Rule mới: Nếu dữ liệu là {original_data} thì quyết định phải được điều chỉnh tích cực hơn."

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info("Đang đánh giá nguyên nhân bằng LLM")
        
        fuzzy_reason = data.get("nguyên nhân quyết định", "")
        
        prompt = f"Bạn là một chuyên gia. Dữ liệu là {data}. Quyết định được đưa ra vì: {fuzzy_reason}. Nguyên nhân này có hợp lý không? Chỉ trả lời TRUE hoặc FALSE."
        
        llm_response = self._call_llm_api(prompt)
        
        if "FALSE" in llm_response:
            data['bất thường'] = True
            data['nguyên nhân bất thường'] = "LLM đánh giá nguyên nhân của hệ thống mờ không hợp lý so với bối cảnh dữ liệu."
            data['đề xuất_rule'] = self.propose_new_rule(data, fuzzy_reason)
        else:
            data['bất thường'] = False
            data['nguyên nhân bất thường'] = None
            
        return data
